import ollama
from typing import List, Dict, AsyncGenerator
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMService:
    """
    Service for interacting with Ollama LLM.
    
    This service handles:
    - Chat completions (streaming and non-streaming)
    - System prompt management
    - Error handling
    - Health checks
    """
    
    # System prompt defines the AI's behavior and personality
    # 🆕 UPDATED: Added RAG awareness
    SYSTEM_PROMPT = r"""You are CodeMentor, an expert programming tutor specializing in helping students prepare for coding exams and interviews.

Your expertise includes:
- Programming fundamentals across multiple languages
- Data structures and algorithms
- Object-oriented programming concepts
- Common exam patterns and question types
- Clear explanations with concrete examples

Your teaching style:
- Explain concepts clearly with step-by-step reasoning
- Provide compilable code examples
- Highlight common mistakes and edge cases
- Use the Socratic method when appropriate
- Be concise but thorough

Guidelines:
- Always use markdown for code blocks with proper syntax highlighting
- Break down complex topics into digestible parts
- Encourage critical thinking
- Adapt explanations to the student's level
- Focus on understanding, not just memorization

When explaining concepts:
- Use clear, structured explanations
- Provide practical code examples
- For mathematical expressions, ALWAYS use LaTeX notation:
  - Inline math: $expression$ (e.g., $O(n^2)$, $O(\log n)$)
  - Block math: $$expression$$ for standalone formulas
- Use markdown for formatting (headers, bold, lists, code blocks)

Code formatting rules (IMPORTANT):
- Use triple backticks with the appropriate language tag for ALL multi-line code blocks: ```python, ```java, ```javascript, ```cpp etc.
- Use single backticks for short inline expressions, variable names, method calls, and single-line snippets: `myVariable`, `print("Hello")`, `console.log(x)`
- Never wrap a single expression or one-liner in triple backticks
- Never use triple backticks without a language tag

🆕 Using Reference Materials:
- When reference materials from the student's uploaded documents are provided, prioritize them in your explanations
- Cite specific concepts from the provided materials when relevant
- If the materials don't fully answer the question, supplement with your general knowledge
- Always ground your answers in the student's own study materials when available

Remember: Your goal is to help students truly understand concepts, not just pass exams."""

    def __init__(self):
        """Initialize the LLM service with configured model"""
        self.model = settings.OLLAMA_MODEL
        self.host = settings.OLLAMA_HOST
        logger.info(f"🤖 LLM Service initialized with model: {self.model}")
    
    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
        """
        Send a chat request to Ollama (non-streaming).
        
        Args:
            messages: List of message dicts with 'role' and 'content'
                     Example: [{"role": "user", "content": "Explain loops"}]
            temperature: Sampling temperature (0.0 = deterministic, 1.0 = creative)
        
        Returns:
            Complete response as a string
        
        Raises:
            Exception: If Ollama is not accessible or request fails
        """
        try:
            # Prepend system prompt to guide the AI's behavior
            full_messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                *messages  # Unpack user's messages
            ]
            
            logger.info(f"💬 Sending chat request with {len(messages)} message(s)")
            
            # Call Ollama API
            response = ollama.chat(
                model=self.model,
                messages=full_messages,
                options={
                    "temperature": temperature,
                    "top_p": 0.9,  # Nucleus sampling
                    "top_k": 40,   # Top-k sampling
                }
            )
            
            # Extract content from response
            content = response['message']['content']
            logger.info(f"✅ Received response ({len(content)} chars)")
            return content
            
        except Exception as e:
            logger.error(f"❌ LLM error: {e}")
            raise Exception(f"Failed to get LLM response: {str(e)}")
    
    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat responses from Ollama token-by-token.
        
        This is better for UX - users see responses appearing in real-time
        instead of waiting for the complete response.
        
        Args:
            messages: List of message dicts
            temperature: Sampling temperature
        
        Yields:
            Response chunks as they're generated
        """
        try:
            # Prepend system prompt
            full_messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                *messages
            ]
            
            logger.info(f"🌊 Starting streaming chat with {len(messages)} message(s)")
            
            # Call Ollama with streaming enabled
            response = ollama.chat(
                model=self.model,
                messages=full_messages,
                stream=True,  # This is the key difference!
                options={
                    "temperature": temperature,
                    "top_p": 0.9,
                    "top_k": 40,
                }
            )
            
            # Yield each chunk as it arrives
            chunk_count = 0
            for chunk in response:
                if 'message' in chunk and 'content' in chunk['message']:
                    content = chunk['message']['content']
                    chunk_count += 1
                    yield content
            
            logger.info(f"✅ Streaming complete ({chunk_count} chunks)")
            
        except Exception as e:
            logger.error(f"❌ Streaming error: {e}")
            yield f"Error: {str(e)}"
    
    def health_check(self) -> bool:
        """
        Check if Ollama service is accessible.
        
        Returns:
            True if Ollama is running and accessible, False otherwise
        """
        try:
            # Try to list available models
            ollama.list()
            logger.info("✅ Ollama health check passed")
            return True
        except Exception as e:
            logger.error(f"❌ Ollama health check failed: {e}")
            return False


# Create a singleton instance
# This ensures we only create one LLMService for the entire application
llm_service = LLMService()
