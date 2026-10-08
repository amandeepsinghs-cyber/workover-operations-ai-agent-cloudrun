import React, { useEffect, useRef, useState } from 'react';
import { FileText, Loader2, Printer, X, AlertTriangle } from 'lucide-react';
import { getPersona } from '../../state/persona';

interface FieldReportOverlayProps {
  wellId: string;
  /** Optional job code; the backend defaults to the top-ranked recommendation. */
  intervention?: string | null;
  onClose: () => void;
}

/**
 * Step 5 (v0.5): printable field report (Pre-field Well Pack) in a full-screen overlay.
 * The HTML is fetched with the X-Persona header (an iframe src cannot send it), then shown via srcDoc,
 * which keeps relative asset paths (/brand/ongc_logo.svg) resolving against the app origin.
 * Esc closes it — also when focus is inside the report.
 */
export const FieldReportOverlay: React.FC<FieldReportOverlayProps> = ({ wellId, intervention, onClose }) => {
  const [html, setHtml] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const frameRef = useRef<HTMLIFrameElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    let cancelled = false;
    setHtml(null);
    setError(null);
    const qs = intervention ? `?intervention=${encodeURIComponent(intervention)}` : '';
    fetch(`/api/wells/${encodeURIComponent(wellId)}/report${qs}`, { headers: { 'X-Persona': getPersona() } })
      .then(async (r) => {
        if (!r.ok) throw new Error(r.status === 404 ? `Unknown well ${wellId}` : `Report unavailable (${r.status})`);
        return r.text();
      })
      .then((t) => !cancelled && setHtml(t))
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      cancelled = true;
    };
  }, [wellId, intervention]);

  // Esc closes the report before any panel / agent Esc handler sees it.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      e.stopImmediatePropagation();
      closeRef.current();
    };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, []);

  const onFrameLoad = () => {
    const w = frameRef.current?.contentWindow;
    w?.addEventListener('keydown', (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeRef.current();
    });
  };

  return (
    <div
      className="fixed inset-0 z-[1200] flex flex-col bg-black/70 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label={`Field report ${wellId}`}
    >
      <div className="flex items-center gap-3 px-4 py-2 bg-[#0d1117] border-b border-border">
        <FileText className="w-4 h-4 text-accent" />
        <span className="text-sm font-semibold text-white">Field report</span>
        <span className="text-xs font-mono text-textMuted">{wellId}</span>
        <div className="ml-auto flex items-center gap-2">
          <button
            type="button"
            onClick={() => frameRef.current?.contentWindow?.print()}
            disabled={!html}
            className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded border border-accent/50 text-accent hover:bg-accent/20 disabled:opacity-40"
            title="Print or save as PDF"
          >
            <Printer className="w-3.5 h-3.5" /> Print
          </button>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded text-textMuted hover:text-white hover:bg-surface"
            title="Close (Esc)"
            aria-label="Close field report"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
      <div className="flex-1 min-h-0 p-3">
        {error ? (
          <div className="h-full flex items-center justify-center gap-2 text-sm text-red-300">
            <AlertTriangle className="w-4 h-4" /> {error}
          </div>
        ) : !html ? (
          <div className="h-full flex items-center justify-center gap-2 text-sm text-textMuted">
            <Loader2 className="w-4 h-4 animate-spin" /> Preparing field report…
          </div>
        ) : (
          <iframe
            ref={frameRef}
            title={`Field report ${wellId}`}
            srcDoc={html}
            onLoad={onFrameLoad}
            className="w-full h-full rounded bg-white shadow-2xl"
          />
        )}
      </div>
    </div>
  );
};
