import React, { useEffect, useState, useCallback, useRef } from 'react';
import { fetchDocuments, uploadDocument, deleteDocument, askDocuments } from '../../services/readerApi';
import { SkeletonList } from '../ui/Skeleton';

function Sym({ name, className = '', fill = false }) {
  return <span className={`material-symbols-outlined ${fill ? 'msym-fill' : ''} ${className}`}>{name}</span>;
}

const KIND = {
  insurance:    { icon: 'shield',       tile: 'bg-g-blue/15 text-g-blue' },
  report:       { icon: 'lab_panel',    tile: 'bg-g-green/15 text-g-green' },
  prescription: { icon: 'medication',   tile: 'bg-g-red/15 text-g-red' },
  document:     { icon: 'description',  tile: 'bg-g-yellow/15 text-g-yellow' },
};

export default function ReaderView({ userId }) {
  const [docs, setDocs] = useState(null);
  const [label, setLabel] = useState('');
  const [uploading, setUploading] = useState(false);
  const [err, setErr] = useState('');
  const [question, setQuestion] = useState('');
  const [asking, setAsking] = useState(false);
  const [result, setResult] = useState(null);
  const fileRef = useRef(null);

  const load = useCallback(() => { fetchDocuments(userId).then(setDocs); }, [userId]);
  useEffect(() => { load(); }, [load]);

  async function onFile(e) {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setErr(''); setUploading(true);
    try {
      await uploadDocument(userId, file, label.trim());
      setLabel('');
      await load();
    } catch (ex) {
      setErr(ex.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  }

  async function remove(id) {
    if (!window.confirm('Remove this document?')) return;
    await deleteDocument(userId, id);
    load();
  }

  async function ask(q) {
    const query = (q ?? question).trim();
    if (!query) return;
    setAsking(true); setResult(null); setErr('');
    try {
      const res = await askDocuments(userId, query);
      setResult({ question: query, ...res });
    } catch {
      setErr('Could not answer right now.');
    } finally {
      setAsking(false);
    }
  }

  const list = docs || [];
  const hasReady = list.some((d) => d.status === 'ready');

  return (
    <div className="flex-1 overflow-y-auto px-8 py-7 bg-background">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-start gap-3 mb-1">
          <div className="w-10 h-10 rounded-xl intelligence-gradient flex items-center justify-center shrink-0">
            <Sym name="auto_stories" className="text-white text-[22px]" fill />
          </div>
          <div>
            <h1 className="font-headline-lg text-[24px] text-on-surface">Reader</h1>
            <p className="text-[14px] text-on-surface-variant">Upload insurance policies, medical reports or prescriptions — then ask questions and get answers straight from them.</p>
          </div>
        </div>

        {/* Upload */}
        <div className="mt-5 bg-surface-container-lowest border border-outline-variant rounded-card p-4 flex flex-wrap items-center gap-3">
          <input value={label} onChange={(e) => setLabel(e.target.value)}
            placeholder="Label (optional) — e.g. “Amma insurance”, “diabetes report”"
            className="flex-1 min-w-[200px] bg-surface-container-low border border-outline-variant focus:border-primary focus:ring-4 focus:ring-primary/10 rounded-xl px-4 py-2.5 text-[14px] text-on-surface outline-none transition" />
          <input ref={fileRef} type="file" accept="application/pdf,image/png,image/jpeg,image/webp" onChange={onFile} className="hidden" />
          <button onClick={() => fileRef.current?.click()} disabled={uploading}
            className="flex items-center gap-2 px-5 py-2.5 rounded-full intelligence-gradient text-white font-semibold text-[14px] shadow-sm hover:brightness-105 active:scale-95 transition disabled:opacity-60">
            <Sym name={uploading ? 'progress_activity' : 'upload'} className={`text-[20px] ${uploading ? 'animate-spin' : ''}`} />
            {uploading ? 'Reading…' : 'Upload document'}
          </button>
        </div>
        {err && <div className="text-error text-[13px] mt-2">{err}</div>}
        <p className="text-[11.5px] text-on-surface-variant/70 mt-2">PDF or image (PNG/JPG), up to 12 MB. Scans and photos are read automatically.</p>

        {/* Ask */}
        {hasReady && (
          <div className="mt-6 bg-surface-container-lowest border border-outline-variant rounded-card p-4">
            <div className="flex items-center gap-2.5">
              <input value={question} onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') ask(); }}
                placeholder="Ask your documents… e.g. “What's my room-rent limit?”"
                className="flex-1 bg-surface-container-low border border-outline-variant focus:border-primary focus:ring-4 focus:ring-primary/10 rounded-action px-5 py-3 text-on-surface outline-none transition" />
              <button onClick={() => ask()} disabled={asking}
                className="w-12 h-12 rounded-full intelligence-gradient text-white flex items-center justify-center shadow-md hover:scale-105 active:scale-95 transition shrink-0 disabled:opacity-60">
                <Sym name={asking ? 'progress_activity' : 'send'} className={`text-[22px] ${asking ? 'animate-spin' : ''}`} fill />
              </button>
            </div>

            {result && (
              <div className="mt-4 border-t border-outline-variant/60 pt-4">
                <div className="text-[13px] font-semibold text-on-surface-variant mb-1">{result.question}</div>
                <div className="text-[14.5px] text-on-surface leading-relaxed whitespace-pre-line">{result.answer}</div>
                {result.sources?.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-3">
                    {result.sources.map((s, i) => (
                      <span key={i} title={s.snippet}
                        className="inline-flex items-center gap-1 text-[11.5px] text-on-surface-variant bg-surface-container px-2.5 py-1 rounded-full border border-outline-variant/60">
                        <Sym name="description" className="text-[14px] text-primary" />{s.label}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Documents */}
        <h2 className="font-title-lg text-[15px] text-on-surface mt-7 mb-3">Your documents</h2>
        {docs === null ? (
          <SkeletonList count={2} />
        ) : list.length === 0 ? (
          <div className="rounded-card border border-dashed border-outline-variant bg-surface-container-low p-10 text-center text-on-surface-variant">
            <Sym name="folder_open" className="text-[34px] text-on-surface-variant/60 mb-2" />
            <p className="text-[14px]">No documents yet. Upload a policy or report above to start asking questions.</p>
          </div>
        ) : (
          <div className="grid gap-3 m3-stagger" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))' }}>
            {list.map((d) => {
              const k = KIND[d.kind] || KIND.document;
              return (
                <div key={d.id} className="group relative bg-surface-container-lowest border border-outline-variant rounded-card p-4 flex items-start gap-3">
                  <div className={`w-11 h-11 rounded-xl shrink-0 flex items-center justify-center ${k.tile}`}>
                    <Sym name={k.icon} className="text-[22px]" fill />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[14px] font-semibold text-on-surface truncate">{d.label || d.filename}</div>
                    <div className="text-[12px] text-on-surface-variant truncate">{d.filename}</div>
                    <div className="mt-1.5">
                      {d.status === 'ready' && <span className="text-[11px] text-g-green-text bg-g-green-tint px-2 py-0.5 rounded-full">Ready · {d.chunk_count} chunks</span>}
                      {d.status === 'processing' && <span className="text-[11px] text-on-surface-variant bg-surface-container px-2 py-0.5 rounded-full">Processing…</span>}
                      {d.status === 'error' && <span className="text-[11px] text-error bg-error-container/50 px-2 py-0.5 rounded-full">Couldn’t read</span>}
                    </div>
                  </div>
                  <button onClick={() => remove(d.id)} title="Remove"
                    className="absolute top-2.5 right-2.5 w-8 h-8 rounded-full bg-surface-container hover:bg-error-container text-on-surface-variant flex items-center justify-center opacity-0 group-hover:opacity-100 transition">
                    <Sym name="delete" className="text-[16px]" />
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
