import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Bot, Maximize2, Minimize2, Minus, PanelRightClose, PanelRightOpen } from 'lucide-react';
import { VoiceAgentPanel, AgentVoiceStatus } from './VoiceAgentPanel';
import type { WellDetail } from '../../types/well';
import type { ChatAction } from '../../api/chat';

interface FloatingAgentProps {
  well?: WellDetail | null;
  field?: string | null;
  screen?: string | null;
  contextLabel?: string;
  onAgentAction?: (a: ChatAction) => void;
  /** Dock automatically as a right column (e.g. while the map or the detail panel is full-screen). */
  autoDock?: boolean;
  /** Reports whether the agent currently occupies the docked right column (so the app can reserve it). */
  onDockedChange?: (docked: boolean) => void;
}

/** Docked command-centre column width: 20% of the screen, never narrower than 340px. */
export const AGENT_DOCK_WIDTH = 'max(20vw, 340px)';

const IDLE: AgentVoiceStatus = { live: false, listening: false, speaking: false, thinking: false };

/**
 * WellPulse AI Agent — floating command centre (bottom-right, every screen).
 * Modelled on the FCC cockpit CopilotLauncher: a launcher pill plus an overlay panel
 * with expand and minimise buttons. The panel stays mounted while minimised so the
 * live voice session and conversation survive minimise and screen changes.
 */
export const FloatingAgent: React.FC<FloatingAgentProps> = ({
  well,
  field,
  screen,
  contextLabel,
  onAgentAction,
  autoDock = false,
  onDockedChange,
}) => {
  const [open, setOpen] = useState<boolean>(false);
  const [expanded, setExpanded] = useState<boolean>(false);
  const [unread, setUnread] = useState<boolean>(false);
  const [voice, setVoice] = useState<AgentVoiceStatus>(IDLE);
  const openRef = useRef(open);
  const launcherRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  // ---- Docked command-centre mode (auto in full-screen, or pinned by the user) ----
  const DOCK_KEY = 'wellpulse.agent.docked';
  const [manualDock, setManualDock] = useState<boolean>(() => {
    try {
      return localStorage.getItem(DOCK_KEY) === '1';
    } catch {
      return false;
    }
  });
  useEffect(() => {
    try {
      localStorage.setItem(DOCK_KEY, manualDock ? '1' : '0');
    } catch {
      /* ignore */
    }
  }, [manualDock]);
  const docked = open && (autoDock || manualDock);
  const dockedRef = useRef(docked);
  useEffect(() => {
    dockedRef.current = docked;
    onDockedChange?.(docked);
  }, [docked, onDockedChange]);

  // ---- Drag to move (position persisted; null = docked bottom-right) ----
  const POS_KEY = 'wellpulse.agent.pos';
  const [pos, setPos] = useState<{ left: number; top: number } | null>(() => {
    try {
      const raw = localStorage.getItem(POS_KEY);
      return raw ? (JSON.parse(raw) as { left: number; top: number }) : null;
    } catch {
      return null;
    }
  });
  const [dragging, setDragging] = useState(false);
  const dragOffset = useRef<{ dx: number; dy: number } | null>(null);

  const clamp = useCallback((left: number, top: number) => {
    const el = panelRef.current;
    const w = el?.offsetWidth ?? 420;
    const h = el?.offsetHeight ?? 640;
    const m = 8;
    return {
      left: Math.min(Math.max(m, left), Math.max(m, window.innerWidth - w - m)),
      top: Math.min(Math.max(m, top), Math.max(m, window.innerHeight - h - m)),
    };
  }, []);

  const onDragStart = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0 || !panelRef.current) return;
    const r = panelRef.current.getBoundingClientRect();
    dragOffset.current = { dx: e.clientX - r.left, dy: e.clientY - r.top };
    e.currentTarget.setPointerCapture(e.pointerId);
    setPos({ left: r.left, top: r.top });
    setDragging(true);
  };
  const onDragMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!dragOffset.current) return;
    setPos(clamp(e.clientX - dragOffset.current.dx, e.clientY - dragOffset.current.dy));
  };
  const onDragEnd = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!dragOffset.current) return;
    dragOffset.current = null;
    setDragging(false);
    if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId);
  };
  const resetPosition = () => setPos(null);

  // Persist position (not on every pixel while dragging).
  useEffect(() => {
    if (dragging) return;
    try {
      if (pos) localStorage.setItem(POS_KEY, JSON.stringify(pos));
      else localStorage.removeItem(POS_KEY);
    } catch {
      /* storage unavailable — position just won't persist */
    }
  }, [pos, dragging]);

  // Keep the panel on-screen after window resize, expand/shrink, or reopening.
  useEffect(() => {
    if (!pos || !open || docked) return;
    const fix = () => setPos((p) => (p ? clamp(p.left, p.top) : p));
    const id = window.setTimeout(fix, 220); // after the size transition
    window.addEventListener('resize', fix);
    return () => {
      window.clearTimeout(id);
      window.removeEventListener('resize', fix);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expanded, open, docked, clamp]);

  useEffect(() => {
    openRef.current = open;
    if (open) setUnread(false);
  }, [open]);

  const minimise = useCallback(() => {
    setOpen(false);
    launcherRef.current?.focus();
  }, []);

  // Keyboard: Ctrl/Cmd+K toggles, "/" opens, Esc minimises (handled before other Esc listeners).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      const typing = !!t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable);
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen((v) => !v);
      } else if (e.key === '/' && !typing && !e.metaKey && !e.ctrlKey) {
        e.preventDefault();
        setOpen(true);
      } else if (e.key === 'Escape' && openRef.current && !dockedRef.current) {
        e.stopImmediatePropagation();
        minimise();
      }
    };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, [minimise]);

  const handleAction = useCallback(
    (a: ChatAction) => {
      if (!openRef.current) setUnread(true);
      onAgentAction?.(a);
    },
    [onAgentAction],
  );

  const handleStatus = useCallback((s: AgentVoiceStatus) => {
    setVoice(s);
    if (!openRef.current && s.speaking) setUnread(true);
  }, []);

  const headerActions = (
    <>
      <button
        type="button"
        onClick={() => setManualDock((v) => !v)}
        disabled={autoDock}
        className={`p-1.5 rounded transition-colors ${
          docked ? 'text-accent' : 'text-textMuted hover:text-white hover:bg-border'
        } disabled:cursor-default`}
        title={
          autoDock
            ? 'Docked while a screen is full-screen'
            : manualDock
            ? 'Undock (float)'
            : 'Dock to the right as command centre'
        }
        aria-label={manualDock ? 'Undock agent panel' : 'Dock agent panel to the right'}
        aria-pressed={docked}
      >
        {docked ? <PanelRightClose className="w-4 h-4" /> : <PanelRightOpen className="w-4 h-4" />}
      </button>
      {!docked && (
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="p-1.5 rounded text-textMuted hover:text-white hover:bg-border transition-colors"
        title={expanded ? 'Shrink' : 'Expand'}
        aria-label={expanded ? 'Shrink agent panel' : 'Expand agent panel'}
      >
        {expanded ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
      </button>
      )}
      <button
        type="button"
        onClick={minimise}
        className="p-1.5 rounded text-textMuted hover:text-white hover:bg-border transition-colors"
        title="Minimise (Esc)"
        aria-label="Minimise WellPulse AI Agent (Esc)"
      >
        <Minus className="w-4 h-4" />
      </button>
    </>
  );

  const voiceBadge = voice.listening ? (
    <span className="flex items-center gap-1 text-[9px] font-mono font-bold text-red-300 bg-red-950/70 border border-red-700/60 px-1.5 py-0.5 rounded animate-pulse">
      ● LISTENING
    </span>
  ) : voice.speaking ? (
    <span className="text-[9px] font-mono font-bold text-accent bg-[#0d1117] border border-accent/50 px-1.5 py-0.5 rounded animate-pulse">
      SPEAKING
    </span>
  ) : voice.thinking ? (
    <span className="text-[9px] font-mono font-bold text-amber-300 bg-amber-950/60 border border-amber-700/60 px-1.5 py-0.5 rounded animate-pulse">
      THINKING
    </span>
  ) : voice.live ? (
    <span className="text-[9px] font-mono font-bold text-emerald-300 bg-emerald-950/60 border border-emerald-700/60 px-1.5 py-0.5 rounded">
      LIVE
    </span>
  ) : (
    <kbd className="text-[9px] font-mono text-textMuted bg-[#0d1117] border border-border px-1 py-0.5 rounded">Ctrl K</kbd>
  );

  return (
    <>
      {/* Agent panel — floating (draggable) or docked as a right-hand command-centre column.
          Hidden, not unmounted, when minimised so voice and history survive. */}
      <div
        ref={panelRef}
        id="wellpulse-agent-panel"
        role={docked ? 'complementary' : 'dialog'}
        aria-label="WellPulse AI Agent"
        aria-modal={docked ? undefined : false}
        style={
          docked
            ? { top: 0, right: 0, bottom: 0, left: 'auto', width: AGENT_DOCK_WIDTH }
            : pos
            ? { left: pos.left, top: pos.top, right: 'auto', bottom: 'auto' }
            : undefined
        }
        className={`fixed z-[1001] flex flex-col overflow-hidden bg-surface ${
          docked
            ? 'border-l border-border shadow-xl shadow-black/40'
            : `right-4 bottom-20 rounded-xl border border-border shadow-2xl shadow-black/60 ${
                dragging ? '' : 'transition-[width,height] duration-200'
              } ${
                expanded
                  ? 'w-[min(760px,calc(100vw-2rem))] h-[calc(100vh-7rem)]'
                  : 'w-[min(420px,calc(100vw-2rem))] h-[min(640px,calc(100vh-7rem))]'
              }`
        } ${open ? '' : 'hidden'}`}
      >
        {!docked && (
          <div
            onPointerDown={onDragStart}
            onPointerMove={onDragMove}
            onPointerUp={onDragEnd}
            onPointerCancel={onDragEnd}
            onDoubleClick={resetPosition}
            className={`h-3.5 shrink-0 flex items-center justify-center bg-[#12161c] border-b border-border/40 select-none touch-none ${
              dragging ? 'cursor-grabbing' : 'cursor-grab'
            }`}
            title="Drag to move · double-click to dock bottom-right"
            aria-label="Move agent panel"
          >
            <span className="w-10 h-1 rounded-full bg-white/20" />
          </div>
        )}
        <VoiceAgentPanel
          well={well}
          field={field}
          screen={screen}
          contextLabel={contextLabel}
          onAgentAction={handleAction}
          onStatusChange={handleStatus}
          headerActions={headerActions}
        />
      </div>

      {/* Launcher pill — hidden while docked (the column has its own minimise) */}
      {!docked && (
        <button
          ref={launcherRef}
          type="button"
          id="wellpulse-agent-launcher"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-controls="wellpulse-agent-panel"
          aria-label={`${open ? 'Minimise' : 'Open'} WellPulse AI Agent${voice.live ? ' — voice live' : ''}`}
          className={`fixed right-4 bottom-4 z-[1001] flex items-center gap-2 pl-2.5 pr-3 py-2 rounded-full border shadow-xl shadow-black/50 transition-colors ${
            open
              ? 'bg-[#12161c] border-border text-textMuted hover:text-white'
              : 'bg-[#12161c] border-accent/60 text-white hover:border-accent'
          }`}
        >
          <span className="relative w-6 h-6 rounded-full bg-accent/20 border border-accent/50 flex items-center justify-center">
            <Bot className="w-3.5 h-3.5 text-accent" />
            {unread && !open && (
              <span className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-accent border-2 border-[#12161c]" />
            )}
          </span>
          <span className="text-xs font-semibold font-sans">{open ? 'Minimise' : 'WellPulse AI Agent'}</span>
          {!open && voiceBadge}
        </button>
      )}
    </>
  );
};
