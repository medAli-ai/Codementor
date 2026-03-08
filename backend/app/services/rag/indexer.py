"""
Indexer Service

Processes PDFs and indexes them into Qdrant vector database.

Pipeline:
1. Extract structured elements from PDF (code blocks, tables, prose)
2. Route elements by type: code/tables stay whole, prose → semantic chunker
3. Map all chunks to page numbers
4. Generate embeddings (sentence-transformers)
5. Upload to Qdrant with metadata including chunk_type
"""
import logging
import pymupdf  # PyMuPDF (fitz)
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional
import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue
)

from app.core.config import settings
from app.services.rag.embedder import get_embedder
from app.services.rag.chunker import get_chunker

logger = logging.getLogger(__name__)

# Monospace font families used for code rendering in PDFs
MONOSPACE_FONTS = {
    "courier", "consolas", "menlo", "monaco",
    "sourcecodepro", "source code pro",
    "firacode", "fira code", "firamono", "fira mono",
    "robotomono", "roboto mono",
    "dejavusansmono", "dejavu sans mono",
    "liberationmono", "liberation mono",
    "lucidaconsole", "lucida console",
    "andalemono", "andale mono",
    "ubuntumono", "ubuntu mono",
    "droidsansmono", "droid sans mono",
    "inconsolata", "jetbrainsmono", "jetbrains mono",
    "hack", "noto mono", "notomono",
    # TeX / LaTeX monospace fonts
    "cmtt", "lmtt", "latin modern mono", "txtt", "zi4",
}


@dataclass
class PDFElement:
    """A typed element extracted from a PDF page."""
    type: str           # "prose" | "code" | "table"
    text: str           # the extracted text content
    page_num: int       # source page number (1-indexed)
    bbox: tuple = None  # (x0, y0, x1, y1) bounding box for overlap detection


def _is_monospace_font(font_name: str) -> bool:
    """
    Check if a font name indicates a monospace/code font.
    
    Normalizes the font name (lowercase, strip common suffixes like -Bold)
    and checks against known monospace font families.
    """
    if not font_name:
        return False
    
    # Normalize: lowercase, remove common suffixes
    normalized = font_name.lower()
    for suffix in ["-bold", "-italic", "-bolditalic", "-regular",
                   ",bold", ",italic", ",bolditalic",
                   "-boldoblique", "-oblique"]:
        normalized = normalized.replace(suffix, "")
    
    # Strip trailing digits and hyphens
    normalized = normalized.rstrip("0123456789-_ ")
    
    # Check exact match or prefix match against known families
    for mono_font in MONOSPACE_FONTS:
        if normalized == mono_font or normalized.startswith(mono_font):
            return True
    
    return False


def _rects_overlap(r1: tuple, r2: tuple, margin: float = 2.0) -> bool:
    """
    Check if two bounding boxes overlap (with small margin).
    
    Args:
        r1, r2: (x0, y0, x1, y1) tuples
        margin: Pixel tolerance for overlap
    """
    return not (
        r1[2] < r2[0] - margin or  # r1 is left of r2
        r1[0] > r2[2] + margin or  # r1 is right of r2
        r1[3] < r2[1] - margin or  # r1 is above r2
        r1[1] > r2[3] + margin     # r1 is below r2
    )


class Indexer:
    """
    Index PDFs into Qdrant vector database.
    
    Extracts structured elements (code, tables, prose) and chunks
    them appropriately: code/tables stay whole, prose gets semantic chunking.
    """
    
    def __init__(
        self,
        qdrant_url: str = None,
        collection_name: str = None
    ):
        self.qdrant_url = qdrant_url or settings.QDRANT_URL
        self.collection_name = collection_name or settings.QDRANT_COLLECTION
        
        logger.info(f"📊 Initializing Indexer:")
        logger.info(f"   Qdrant URL: {self.qdrant_url}")
        logger.info(f"   Collection: {self.collection_name}")
        
        try:
            self.client = QdrantClient(url=self.qdrant_url)
            self.embedder = get_embedder()
            self.chunker = get_chunker()
            logger.info(f"✅ Indexer initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize indexer: {e}")
            raise
    
    # ──────────────────────────────────────────────────────────────────────
    # EXTRACTION: Structured element extraction from PDF
    # ──────────────────────────────────────────────────────────────────────
    
    def extract_pdf_elements(self, pdf_path: str) -> tuple[list[PDFElement], dict]:
        """
        Extract typed elements (code, tables, prose) from a PDF.
        
        Per page, extraction order:
        1. Tables (via find_tables) — mark regions as claimed
        2. Code blocks (via monospace font detection) — mark regions as claimed
        3. Prose (everything else)
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Tuple of (elements list, metadata dict)
        """
        try:
            logger.info(f"📄 Extracting structured elements from: {pdf_path}")
            
            doc = pymupdf.open(pdf_path)
            
            metadata = {
                "pages_count": len(doc),
                "file_size_bytes": Path(pdf_path).stat().st_size,
            }
            
            all_elements = []
            stats = {"code": 0, "table": 0, "prose": 0}
            
            for page_num, page in enumerate(doc, 1):
                page_elements = self._extract_page_elements(page, page_num)
                all_elements.extend(page_elements)
                for el in page_elements:
                    stats[el.type] += 1
            
            doc.close()
            
            logger.info(f"✅ Extracted {len(all_elements)} elements from {metadata['pages_count']} pages")
            logger.info(f"   Code blocks: {stats['code']}, Tables: {stats['table']}, Prose: {stats['prose']}")
            
            return all_elements, metadata
            
        except Exception as e:
            logger.error(f"❌ PDF extraction failed: {e}")
            raise
    
    def _extract_page_elements(self, page, page_num: int) -> list[PDFElement]:
        """
        Extract typed elements from a single page.

        Order: tables first → code blocks → prose (remaining text).
        Claimed regions prevent double-counting.

        Parses page.get_text("dict") once and passes the block list
        to both code and prose extractors to avoid redundant parsing.
        """
        elements = []
        claimed_regions = []  # list of (x0, y0, x1, y1) bboxes

        # Parse page structure once — shared by code + prose extractors
        page_dict_blocks = page.get_text("dict")["blocks"]

        # ── 1. Extract tables ────────────────────────────────────────────
        table_elements = self._extract_tables(page, page_num)
        for el in table_elements:
            elements.append(el)
            if el.bbox:
                claimed_regions.append(el.bbox)

        # ── 2. Extract code blocks (monospace font spans) ────────────────
        code_elements = self._extract_code_blocks(
            page_dict_blocks, page_num, claimed_regions
        )
        for el in code_elements:
            elements.append(el)
            if el.bbox:
                claimed_regions.append(el.bbox)

        # ── 3. Extract prose (everything not claimed) ────────────────────
        prose_elements = self._extract_prose(
            page_dict_blocks, page_num, claimed_regions
        )
        elements.extend(prose_elements)

        return elements
    
    def _extract_tables(self, page, page_num: int) -> list[PDFElement]:
        """Extract tables using PyMuPDF's built-in table detection."""

        # Quick pre-check: skip expensive layout analysis if no ruling lines
        if not self._page_has_table_indicators(page):
            logger.debug(f"   Skipping table detection on page {page_num}: no line drawings")
            return elements
        elements = []
        
        try:
            tables = page.find_tables()
            
            for table in tables:
                # Extract table as text rows
                rows = table.extract()
                if not rows:
                    continue
                
                # Format as readable text (pipe-separated)
                text_rows = []
                for row in rows:
                    # Replace None cells with empty string
                    clean_row = [str(cell).strip() if cell else "" for cell in row]
                    text_rows.append(" | ".join(clean_row))
                
                table_text = "\n".join(text_rows).strip()
                
                if table_text and len(table_text) > 10:
                    elements.append(PDFElement(
                        type="table",
                        text=table_text,
                        page_num=page_num,
                        bbox=table.bbox
                    ))
                    
        except Exception as e:
            logger.debug(f"   Table extraction failed on page {page_num}: {e}")
        
        return elements
    
    @staticmethod
    def _page_has_table_indicators(page) -> bool:
        """
        Quick check for ruling lines that indicate table presence.

        Tables in PDFs are almost always rendered with horizontal/vertical
        lines ("l") or rectangles ("re"). Pages without these drawing
        commands overwhelmingly have no tables, so we can skip the
        expensive find_tables() layout analysis.
        """
        try:
            for drawing in page.get_drawings():
                for item in drawing["items"]:
                    if item[0] in ("l", "re"):  # line or rectangle
                        return True
        except Exception:
            return True  # if check fails, fall through to find_tables()
        return False
    
    def _extract_code_blocks(
        self, blocks: list, page_num: int, claimed_regions: list
    ) -> list[PDFElement]:
        """
        Detect code blocks by scanning for monospace font spans.
        
        Groups consecutive monospace blocks into single code elements.
        Skips regions already claimed by tables.
        """
        elements = []
        
        try:
            
            
            # Collect monospace blocks
            mono_blocks = []  # list of {"text": ..., "bbox": ...}
            
            for block in blocks:
                if block["type"] != 0:  # only text blocks
                    continue
                
                block_bbox = tuple(block["bbox"])
                
                # Skip if overlaps with a claimed region (table)
                if any(_rects_overlap(block_bbox, cr) for cr in claimed_regions):
                    continue
                
                # Check if this block is predominantly monospace
                total_chars = 0
                mono_chars = 0
                block_lines = []
                
                for line in block["lines"]:
                    line_text_parts = []
                    for span in line["spans"]:
                        text = span["text"]
                        char_count = len(text)
                        total_chars += char_count
                        if _is_monospace_font(span["font"]):
                            mono_chars += char_count
                        line_text_parts.append(text)
                    
                    line_text = "".join(line_text_parts).rstrip()
                    if line_text:
                        block_lines.append(line_text)
                
                # A block is "code" if >70% of its characters are monospace
                if total_chars > 0 and mono_chars / total_chars > 0.7:
                    block_text = "\n".join(block_lines).strip()
                    if block_text:
                        mono_blocks.append({
                            "text": block_text,
                            "bbox": block_bbox,
                            "y0": block_bbox[1],
                        })
            
            # Group consecutive monospace blocks into code elements
            # "Consecutive" = vertically close (within 15px gap)
            if mono_blocks:
                mono_blocks.sort(key=lambda b: b["y0"])
                
                groups = []
                current_group = [mono_blocks[0]]
                
                for block in mono_blocks[1:]:
                    prev = current_group[-1]
                    prev_bottom = prev["bbox"][3]
                    curr_top = block["bbox"][1]
                    
                    # If close vertically, merge into same code block
                    if curr_top - prev_bottom < 15:
                        current_group.append(block)
                    else:
                        groups.append(current_group)
                        current_group = [block]
                
                groups.append(current_group)
                
                # Convert groups to elements
                for group in groups:
                    text = "\n".join(b["text"] for b in group).strip()
                    
                    if text and len(text) > 5:
                        # Compute merged bounding box
                        x0 = min(b["bbox"][0] for b in group)
                        y0 = min(b["bbox"][1] for b in group)
                        x1 = max(b["bbox"][2] for b in group)
                        y1 = max(b["bbox"][3] for b in group)
                        
                        elements.append(PDFElement(
                            type="code",
                            text=text,
                            page_num=page_num,
                            bbox=(x0, y0, x1, y1)
                        ))
                        
        except Exception as e:
            logger.debug(f"   Code extraction failed on page {page_num}: {e}")
        
        return elements
    
    def _extract_prose(
        self, blocks: list, page_num: int, claimed_regions: list
    ) -> list[PDFElement]:
        """
        Extract non-code, non-table text as prose.
        
        Uses get_text("dict") to filter out blocks that overlap
        with already-claimed regions.
        """
        elements = []
        
        try:
            prose_parts = []
            
            for block in blocks:
                if block["type"] != 0:
                    continue
                
                block_bbox = tuple(block["bbox"])
                
                # Skip if overlaps with any claimed region
                if any(_rects_overlap(block_bbox, cr) for cr in claimed_regions):
                    continue
                
                # Extract text from this block
                block_lines = []
                for line in block["lines"]:
                    line_text = "".join(span["text"] for span in line["spans"]).strip()
                    if line_text:
                        block_lines.append(line_text)
                
                if block_lines:
                    prose_parts.append(" ".join(block_lines))
            
            # Combine into a single prose element per page
            prose_text = "\n\n".join(prose_parts).strip()
            
            if prose_text and len(prose_text) > 10:
                elements.append(PDFElement(
                    type="prose",
                    text=prose_text,
                    page_num=page_num,
                    bbox=None  # prose spans the whole page remainder
                ))
                
        except Exception as e:
            logger.debug(f"   Prose extraction failed on page {page_num}: {e}")
        
        return elements
    
    # ──────────────────────────────────────────────────────────────────────
    # CHUNKING: Route elements by type
    # ──────────────────────────────────────────────────────────────────────
    
    def _chunk_elements(
        self, elements: list[PDFElement]
    ) -> list[dict]:
        """
        Chunk elements by type:
        - Code blocks → keep whole (1 element = 1 chunk)
        - Tables → keep whole (1 element = 1 chunk)
        - Prose → concatenate all prose, then semantic chunk with page mapping
        
        Returns list of {"text": ..., "chunk_type": ..., "page_numbers": [...]}
        """
        chunks = []
        
        # Separate elements by type
        code_elements = [e for e in elements if e.type == "code"]
        table_elements = [e for e in elements if e.type == "table"]
        prose_elements = [e for e in elements if e.type == "prose"]
        
        # ── Code: each block = 1 chunk ──────────────────────────────────
        for el in code_elements:
            chunks.append({
                "text": el.text,
                "chunk_type": "code",
                "page_numbers": [el.page_num],
            })
        
        logger.info(f"   Code chunks: {len(code_elements)} (kept whole)")
        
        # ── Tables: each table = 1 chunk ────────────────────────────────
        for el in table_elements:
            chunks.append({
                "text": el.text,
                "chunk_type": "table",
                "page_numbers": [el.page_num],
            })
        
        logger.info(f"   Table chunks: {len(table_elements)} (kept whole)")
        
        # ── Prose: concatenate then semantic chunk ──────────────────────
        if prose_elements:
            # Build full prose text with page boundary tracking
            prose_parts = []
            page_boundaries = []  # [(start_char, page_num), ...]
            current_pos = 0
            
            for el in prose_elements:
                page_boundaries.append((current_pos, el.page_num))
                prose_parts.append(el.text)
                current_pos += len(el.text) + 2  # +2 for "\n\n" separator
            
            full_prose = "\n\n".join(prose_parts)
            
            # Semantic chunk the prose
            prose_chunks = self.chunker.chunk(full_prose)
            
            # Map each chunk back to page number(s)
            search_pos = 0
            for chunk_text in prose_chunks:
                page_numbers, search_pos = self._get_chunk_pages(
                    chunk_text, full_prose, page_boundaries, search_pos
                )
                chunks.append({
                    "text": chunk_text,
                    "chunk_type": "prose",
                    "page_numbers": page_numbers,
                })
            
            logger.info(f"   Prose chunks: {len(prose_chunks)} (semantic chunked from {len(prose_elements)} elements)")
        
        return chunks
    
    def _get_chunk_pages(
        self,
        chunk: str,
        full_text: str,
        page_boundaries: list[tuple[int, int]],
        search_from: int = 0
    ) -> tuple[list[int], int]:
        """
        Map a chunk to its page number(s) using character positions.
        
        Finds the chunk in full_text, then checks which page boundaries
        it overlaps with.
        """
        start = full_text.find(chunk, search_from)
        if start == -1:
            start = full_text.find(chunk)
        if start == -1:
            return [], search_from
        
        end = start + len(chunk)
        
        pages = set()
        for i, (boundary_start, page_num) in enumerate(page_boundaries):
            if i + 1 < len(page_boundaries):
                boundary_end = page_boundaries[i + 1][0]
            else:
                boundary_end = len(full_text)
            
            if start < boundary_end and end > boundary_start:
                pages.add(page_num)
        
        return sorted(pages), end
    
    # ──────────────────────────────────────────────────────────────────────
    # QDRANT: Collection management and upload
    # ──────────────────────────────────────────────────────────────────────
    
    def _ensure_collection(self, collection_name: str, vector_size: int = None):
        """Create Qdrant collection if it doesn't exist."""
        vector_size = vector_size or self.embedder.get_dimension()
        
        try:
            collections = self.client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if collection_name not in collection_names:
                logger.info(f"📦 Creating collection: {collection_name}")
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=vector_size,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"✅ Collection created successfully")
            else:
                logger.info(f"✅ Collection already exists: {collection_name}")
                
        except Exception as e:
            logger.error(f"❌ Failed to ensure collection: {e}")
            raise
    
    # ──────────────────────────────────────────────────────────────────────
    # PIPELINE: Main indexing entry point
    # ──────────────────────────────────────────────────────────────────────
    
    def index_pdf(
        self,
        pdf_path: str,
        collection_name: str,
        metadata: dict
    ) -> int:
        """
        Complete indexing pipeline:
        Extract Elements → Route by Type → Chunk → Embed → Upload.
        
        Args:
            pdf_path: Path to PDF file
            collection_name: Qdrant collection name
            metadata: Additional metadata (user_id, title, is_public, etc.)
        
        Returns:
            Number of chunks indexed
        """
        try:
            logger.info(f"🔄 Starting PDF indexing pipeline")
            logger.info(f"   PDF: {pdf_path}")
            logger.info(f"   Collection: {collection_name}")
            
            # 1. Extract structured elements
            elements, pdf_metadata = self.extract_pdf_elements(pdf_path)
            
            if not elements:
                raise ValueError("No elements extracted from PDF")
            
            # 2. Chunk elements by type
            logger.info(f"✂️  Chunking elements...")
            chunks = self._chunk_elements(elements)
            
            if not chunks:
                raise ValueError("No chunks generated from elements")
            
            logger.info(f"✅ Generated {len(chunks)} total chunks")
            
            # 3. Generate embeddings
            logger.info(f"🧠 Generating embeddings...")
            chunk_texts = [c["text"] for c in chunks]
            embeddings = self.embedder.embed_batch(
                chunk_texts,
                batch_size=32,
                show_progress=True
            )
            
            logger.info(f"✅ Generated {len(embeddings)} embeddings")
            
            # 4. Ensure collection exists
            self._ensure_collection(collection_name)
            
            # 5. Prepare points for Qdrant
            logger.info(f"📊 Preparing points for upload...")
            points = []
            
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                point_metadata = {
                    **metadata,  # user_id, title, is_public, document_id, topic
                    "chunk_index": i,
                    "chunk_text": chunk["text"],
                    "chunk_type": chunk["chunk_type"],
                    "page_numbers": chunk["page_numbers"],
                    "pages_count": pdf_metadata["pages_count"],
                    "file_size_bytes": pdf_metadata["file_size_bytes"],
                }
                
                point = PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding.tolist(),
                    payload=point_metadata
                )
                points.append(point)
            
            # Log type distribution
            type_counts = {}
            for c in chunks:
                t = c["chunk_type"]
                type_counts[t] = type_counts.get(t, 0) + 1
            logger.info(f"📊 Chunk types: {type_counts}")
            
            # 6. Upload to Qdrant
            logger.info(f"⬆️  Uploading {len(points)} points to Qdrant...")
            self.client.upsert(
                collection_name=collection_name,
                points=points,
                wait=True
            )
            
            logger.info(f"✅ Upload complete!")
            logger.info(f"📊 Indexed {len(chunks)} chunks from {pdf_path}")
            
            return len(chunks)
            
        except Exception as e:
            logger.error(f"❌ Indexing failed: {e}")
            raise
    
    def delete_document(
        self,
        collection_name: str,
        document_id: int
    ) -> bool:
        """Delete all chunks for a specific document."""
        try:
            logger.info(f"🗑️  Deleting document {document_id} from {collection_name}")
            
            self.client.delete(
                collection_name=collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=document_id)
                        )
                    ]
                )
            )
            
            logger.info(f"✅ Document {document_id} deleted successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to delete document: {e}")
            return False


# Singleton instance
_indexer_instance = None


def get_indexer() -> Indexer:
    """Get singleton indexer instance."""
    global _indexer_instance
    if _indexer_instance is None:
        _indexer_instance = Indexer()
    return _indexer_instance