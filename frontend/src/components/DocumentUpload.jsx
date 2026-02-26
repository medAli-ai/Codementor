// ============================================================
// DocumentUpload.jsx
// ============================================================
// State machine: idle → dragging → uploading → success | error
// Matches existing color scheme: blue-600, gray-xxx, white bg
// ============================================================

import { useCallback, useRef, useState } from 'react';
import { documentsAPI, DOCUMENT_TOPICS } from '../services/api';

const STATE = {
  IDLE:      'idle',
  DRAGGING:  'dragging',
  UPLOADING: 'uploading',
  SUCCESS:   'success',
  ERROR:     'error',
};

const formatBytes = (bytes) => {
  if (bytes < 1024)       return `${bytes} B`;
  if (bytes < 1024 ** 2)  return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
};

function DocumentUpload({ onSuccess, onCancel }) {
  const [file,          setFile]          = useState(null);
  const [topic,         setTopic]         = useState('');
  const [title,         setTitle]         = useState('');
  const [isPublic,      setIsPublic]      = useState(false);
  const [uploadState,   setUploadState]   = useState(STATE.IDLE);
  const [progress,      setProgress]      = useState(0);
  const [errorMessage,  setErrorMessage]  = useState('');
  const [uploadedDoc,   setUploadedDoc]   = useState(null);

  // dragCounter prevents flicker when hovering over child elements
  const dragCounter = useRef(0);
  const fileInputRef = useRef(null);

  // ── Drag handlers ─────────────────────────────────────────────────────────
  const handleDragEnter = useCallback((e) => {
    e.preventDefault();
    dragCounter.current++;
    setUploadState(STATE.DRAGGING);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    dragCounter.current--;
    if (dragCounter.current === 0) setUploadState(STATE.IDLE);
  }, []);

  const handleDragOver  = useCallback((e) => { e.preventDefault(); }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    dragCounter.current = 0;
    setUploadState(STATE.IDLE);
    const dropped = e.dataTransfer.files[0];
    if (dropped) validateAndSet(dropped);
  }, []);

  // ── File validation ───────────────────────────────────────────────────────
  const validateAndSet = (f) => {
    if (f.type !== 'application/pdf') {
      setErrorMessage('Only PDF files are supported.');
      setUploadState(STATE.ERROR);
      return;
    }
    if (f.size > 50 * 1024 * 1024) {
      setErrorMessage('File must be smaller than 50 MB.');
      setUploadState(STATE.ERROR);
      return;
    }
    setFile(f);
    setErrorMessage('');
    setUploadState(STATE.IDLE);
  };

  // ── Submit ────────────────────────────────────────────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file || !topic) return;

    setUploadState(STATE.UPLOADING);
    setProgress(0);

    try {
      const response = await documentsAPI.upload(file, topic, title, isPublic, setProgress);
      setUploadedDoc(response.data);
      setUploadState(STATE.SUCCESS);
      onSuccess?.(response.data);
    } catch (err) {
      const detail = err.response?.data?.detail;
      const msg = Array.isArray(detail)
        ? detail.map(e => e.msg).join(', ')
        : detail || 'Upload failed. Please try again.';
      setErrorMessage(msg);
    }
  };

  const handleReset = () => {
    setFile(null); setTopic(''); setTitle(''); setIsPublic(false);
    setUploadState(STATE.IDLE); setProgress(0);
    setErrorMessage(''); setUploadedDoc(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="bg-white rounded-2xl shadow-xl p-6 w-full max-w-lg border border-gray-200">

      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-lg font-semibold text-gray-800">Upload Document</h2>
        {onCancel && (
          <button
            onClick={onCancel}
            className="text-gray-400 hover:text-gray-600 text-xl leading-none"
          >×</button>
        )}
      </div>

      {/* ── SUCCESS ─────────────────────────────────────────────────────── */}
      {uploadState === STATE.SUCCESS && uploadedDoc && (
        <div className="flex flex-col items-center gap-4 py-6 text-center">
          <div className="text-5xl">✅</div>
          <div>
            <p className="font-semibold text-gray-800">Upload successful!</p>
            <p className="text-sm text-gray-500 mt-1">
              <strong>{uploadedDoc.title}</strong> is being processed and will
              appear in your library shortly.
            </p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={handleReset}
              className="border border-gray-200 rounded-lg px-4 py-2 text-sm text-gray-600 hover:bg-gray-50"
            >Upload another</button>
            {onCancel && (
              <button
                onClick={onCancel}
                className="bg-blue-600 text-white rounded-lg px-4 py-2 text-sm font-medium hover:bg-blue-700"
              >Done</button>
            )}
          </div>
        </div>
      )}

      {/* ── UPLOADING ───────────────────────────────────────────────────── */}
      {uploadState === STATE.UPLOADING && (
        <div className="flex flex-col items-center gap-4 py-8">
          <div className="text-3xl animate-spin">⏳</div>
          <div className="w-full">
            <div className="flex justify-between text-xs text-gray-500 mb-1">
              <span>Uploading {file?.name}</span>
              <span>{progress}%</span>
            </div>
            <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-2 bg-blue-600 rounded-full transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="text-xs text-gray-400 text-center mt-2">
              {progress < 100
                ? 'Transferring file…'
                : 'Processing — indexing chunks in the background…'}
            </p>
          </div>
        </div>
      )}

      {/* ── FORM (idle / dragging / error) ──────────────────────────────── */}
      {uploadState !== STATE.SUCCESS && uploadState !== STATE.UPLOADING && (
        <form onSubmit={handleSubmit} className="space-y-4">

          {/* Drop zone */}
          <div
            onDragEnter={handleDragEnter}
            onDragLeave={handleDragLeave}
            onDragOver={handleDragOver}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`
              border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors
              ${uploadState === STATE.DRAGGING
                ? 'border-blue-400 bg-blue-50'
                : 'border-gray-300 bg-gray-50 hover:border-blue-400 hover:bg-blue-50'}
            `}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,application/pdf"
              className="sr-only"
              onChange={(e) => { const f = e.target.files[0]; if (f) validateAndSet(f); }}
            />

            {file ? (
              <div className="flex items-center justify-center gap-3">
                <span className="text-2xl">📄</span>
                <div className="text-left">
                  <p className="text-sm font-medium text-gray-800 truncate max-w-xs">{file.name}</p>
                  <p className="text-xs text-gray-500">{formatBytes(file.size)}</p>
                </div>
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); handleReset(); }}
                  className="text-gray-400 hover:text-gray-600 ml-2"
                >✕</button>
              </div>
            ) : (
              <>
                <p className="text-2xl mb-2">
                  {uploadState === STATE.DRAGGING ? '📂' : '📁'}
                </p>
                <p className="text-sm font-medium text-gray-700">
                  {uploadState === STATE.DRAGGING ? 'Drop it here!' : 'Drop PDF here or click to browse'}
                </p>
                <p className="text-xs text-gray-400 mt-1">PDF only · Max 50 MB</p>
              </>
            )}
          </div>

          {/* Error */}
          {uploadState === STATE.ERROR && errorMessage && (
            <div className="bg-red-50 border border-red-200 text-red-600 rounded-lg px-3 py-2 text-sm">
              ❌ {errorMessage}
            </div>
          )}

          {/* Topic */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Topic <span className="text-red-500">*</span>
            </label>
            <select
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              required
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select a topic…</option>
              {DOCUMENT_TOPICS.map(t => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>

          {/* Title */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Title <span className="text-gray-400 font-normal">(optional)</span>
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Think Java — Chapter 5"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm text-gray-800 placeholder-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <p className="text-xs text-gray-400 mt-1">Defaults to the PDF filename.</p>
          </div>

          {/* Public toggle */}
          <div className="flex items-center justify-between border border-gray-200 rounded-lg px-3 py-2.5">
            <div>
              <p className="text-sm font-medium text-gray-700">Make public</p>
              <p className="text-xs text-gray-400">Allow other students to benefit from this document</p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={isPublic}
              onClick={() => setIsPublic(v => !v)}
              className={`
                relative inline-flex h-6 w-11 rounded-full border-2 border-transparent
                transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
                ${isPublic ? 'bg-blue-600' : 'bg-gray-200'}
              `}
            >
              <span className={`
                inline-block h-5 w-5 rounded-full bg-white shadow transition-transform duration-200
                ${isPublic ? 'translate-x-5' : 'translate-x-0'}
              `} />
            </button>
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={!file || !topic}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl py-2.5 text-sm font-semibold transition-colors"
          >
            Upload Document
          </button>
        </form>
      )}
    </div>
  );
}

export default DocumentUpload;