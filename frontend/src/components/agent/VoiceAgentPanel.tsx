import React, { useState, useEffect, useRef } from 'react';
import {
  Mic,
  MicOff,
  Send,
  Volume2,
  VolumeX,
  Sparkles,
  Bot,
  User,
  Wrench,
  Radio,
  Play,
  Zap,
  Square,
  AlertTriangle,
} from 'lucide-react';
import { ChatMessage, Recommendation, WellDetail } from '../../types/well';
import {
  LiveClient,
  isLiveSupported,
  LiveStatus,
  VoiceState,
  ToolCallEvent,
} from '../../live/liveClient';
import { audioPlayer } from '../../live/audioPlayer';
import {
  postChat,
  ChatAction,
  ChatArtifact as ChatArtifactType,
  isExplicitDetailRequest,
  pickCanvasView,
} from '../../api/chat';
import { ChatArtifact } from './ChatArtifact';

interface VoiceAgentPanelProps {
  well?: WellDetail | null;
  field?: string | null;
  screen?: string | null;
  onAgentAction?: (a: ChatAction) => void;
  /** Extra header buttons supplied by the floating frame (expand / minimise). */
  headerActions?: React.ReactNode;
  /** Short "what the agent sees" label, e.g. "Lakwa · LKW-019 · Production". */
  contextLabel?: string;
  /** Reports voice state so the minimised launcher can show LIVE / listening / speaking. */
  onStatusChange?: (s: AgentVoiceStatus) => void;
  /** Step 5: open the printable field report overlay for a well. */
  onOpenFieldReport?: (wellId: string) => void;
}

/** Step 5: "prepare the field report / crew pack / printable report for GK-129". */
const FIELD_REPORT_RE =
  /\b(field|crew|site|rig)[\s-]+(report|pack)\b|\bwell[\s-]+pack\b|\breport\s+for\s+(the\s+)?(crew|field|site|rig)\b|\bprint(able)?\s+(the\s+)?report\b/i;
const WELL_ID_RE = /\b([A-Z]{2,3})[\s-]?(\d{3})\b/i;

export interface AgentVoiceStatus {
  live: boolean;
  listening: boolean;
  speaking: boolean;
  thinking: boolean;
}

type AgentLanguage = 'hinglish' | 'english' | 'hindi';

/**
 * Step 4 (UI redesign): data-heavy answers are shown in the right-hand panel, not as cards in the chat.
 * The chat keeps the short spoken/typed answer plus a "↗ Showing in panel" chip that re-opens the view.
 */
const PANEL_ARTIFACTS: Record<string, { screen: ChatAction['screen']; label: string }> = {
  well_profile: { screen: 'well', label: 'Well' },
  well_production_chart: { screen: 'well', label: 'Production' },
  nba: { screen: 'well', label: 'Recommendation' },
  counterfactual: { screen: 'well', label: 'Compare' },
  attribution_waterfall: { screen: 'well', label: 'Diagnosis' },
  intervention_classification: { screen: 'well', label: 'Recommendation' },
  field_history_chart: { screen: 'field_history', label: 'Field history' },
  field_comparison: { screen: 'field_compare', label: 'Field comparison' },
  health_buckets: { screen: 'field_health', label: 'Health & priority' },
  priority_queue: { screen: 'priority', label: 'Priority list' },
  offset_decline: { screen: 'well', label: 'vs Offsets' },
  well_anomalies: { screen: 'well', label: 'History & Wax/Sand' },
  wax_sand: { screen: 'well', label: 'History & Wax/Sand' },
};
const VIEW_LABEL: Record<string, string> = {
  overview: 'Overview',
  production: 'Production',
  interventions: 'Interventions',
  wellbore: 'Wellbore',
  pressures: 'Tests & Pressure',
  diagnosis: 'Diagnosis',
  recommendation: 'Recommendation',
  compare: 'Compare',
  offsets: 'vs Offsets',
  history: 'History & Wax/Sand',
  nearby: 'Nearby',
};

export interface ToolCallInfo {
  name: string;
  status: string;
  duration_ms?: number;
}

// D-1: no currency. Cost band + rig-days may be absent on live/tool payloads.
export interface SafeRecommendation extends Omit<Recommendation, 'cost_band' | 'rig_days'> {
  cost_band?: Recommendation['cost_band'];
  rig_days?: number;
}

export type LiveChatMessage = Omit<ChatMessage, 'recommendation'> & {
  tools?: ToolCallInfo[];
  live?: boolean;
  recommendation?: SafeRecommendation;
  artifacts?: ChatArtifactType[];
  status?: 'ok' | 'degraded';
  /** Step 5: this message is a "↗ Field report · WELL" chip. */
  fieldReportWell?: string;
};

export const VoiceAgentPanel: React.FC<VoiceAgentPanelProps> = ({
  well,
  field,
  screen,
  onAgentAction,
  headerActions,
  contextLabel,
  onStatusChange,
  onOpenFieldReport,
}) => {
  const [messages, setMessages] = useState<LiveChatMessage[]>([]);
  const [inputPrompt, setInputPrompt] = useState<string>('');
  const composerRef = useRef<HTMLTextAreaElement>(null);
  // Shrink the text box back after a message is sent / cleared.
  useEffect(() => {
    if (!inputPrompt && composerRef.current) composerRef.current.style.height = '';
  }, [inputPrompt]);
  const [language, setLanguage] = useState<AgentLanguage>('hinglish');
  const [currentRecommendation, setCurrentRecommendation] = useState<SafeRecommendation | null>(null);

  // Live client states
  const [isLiveMode, setIsLiveMode] = useState<boolean>(() => isLiveSupported());
  const [liveStatus, setLiveStatus] = useState<LiveStatus>('disconnected');
  const [statusInfo, setStatusInfo] = useState<{ model?: string; memory?: boolean; message?: string }>({});
  const [voiceState, setVoiceState] = useState<VoiceState>('idle');
  const [isOpenMic, setIsOpenMic] = useState<boolean>(false);
  const [isTalking, setIsTalking] = useState<boolean>(false);
  const [firstAudioLatency, setFirstAudioLatency] = useState<number | null>(null);

  // Audio / Speech / UI states
  const [isMuted, setIsMuted] = useState<boolean>(false);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);

  // Speech synthesis speaking state (for text mode TTS replay)
  const [legacySpeaking, setLegacySpeaking] = useState<boolean>(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const isTalkingRef = useRef<boolean>(false);
  const currentUserMsgIdRef = useRef<string | null>(null);
  const currentAgentMsgIdRef = useRef<string | null>(null);
  // Latest user utterance (typed or spoken). Agent actions open the full well view only when this
  // explicitly asks for history / deep dive / report (isExplicitDetailRequest).
  const lastUserTextRef = useRef<string>('');

  // Step 5: an explicit "field report / crew pack" request opens the printable report overlay for the
  // well named in the message (or the selected well) and leaves a re-open chip in the chat. Held in a
  // ref so the Live handlers (registered once per well/field) always call the latest version.
  const maybeOpenFieldReport = (text: string) => {
    if (!onOpenFieldReport || !text || !FIELD_REPORT_RE.test(text)) return;
    const m = text.match(WELL_ID_RE);
    const id = m ? `${m[1].toUpperCase()}-${m[2]}` : well?.id;
    if (!id) return;
    onOpenFieldReport(id);
    setMessages((prev) => [
      ...prev,
      {
        id: `report-${Date.now()}`,
        sender: 'agent',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        text: '',
        fieldReportWell: id,
      },
    ]);
  };
  const fieldReportRef = useRef(maybeOpenFieldReport);
  fieldReportRef.current = maybeOpenFieldReport;

  // 1. LiveClient instance per panel in useRef
  const clientRef = useRef<LiveClient | null>(null);
  if (!clientRef.current) {
    clientRef.current = new LiveClient();
  }
  const client = clientRef.current;

  // Set LiveClient event handlers
  useEffect(() => {
    client.setHandlers({
      onStatus: (s, info) => {
        setLiveStatus(s);
        setStatusInfo(info || {});

        if (s === 'resumed' && info?.memory) {
          const resumeMsg: LiveChatMessage = {
            id: `sys-${Date.now()}`,
            sender: 'agent',
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            text: 'Live voice resumed — conversation memory kept.',
            live: true,
          };
          setMessages((prev) => [...prev, resumeMsg]);
        } else if (s === 'fallback') {
          const fbText = info?.message
            ? `Live voice unavailable — switched to text (retry). (${info.message})`
            : 'Live voice unavailable — switched to text (retry).';
          const fbMsg: LiveChatMessage = {
            id: `sys-${Date.now()}`,
            sender: 'agent',
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            text: fbText,
            live: true,
          };
          setMessages((prev) => [...prev, fbMsg]);
        }
      },

      onVoiceState: (s) => {
        setVoiceState(s);
      },

      onInputTranscript: (textDelta) => {
        if (!textDelta) return;
        const msgId = currentUserMsgIdRef.current;
        if (!msgId) {
          lastUserTextRef.current = textDelta;
          const newId = `user-live-${Date.now()}`;
          currentUserMsgIdRef.current = newId;
          const newMsg: LiveChatMessage = {
            id: newId,
            sender: 'user',
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            text: `🎙️ ${textDelta}`,
            live: true,
          };
          setMessages((prev) => [...prev, newMsg]);
        } else {
          lastUserTextRef.current += textDelta;
          setMessages((prev) =>
            prev.map((m) => (m.id === msgId ? { ...m, text: m.text + textDelta } : m))
          );
        }
      },

      onCaptionDelta: (textDelta) => {
        if (!textDelta) return;
        const msgId = currentAgentMsgIdRef.current;
        if (!msgId) {
          const newId = `agent-live-${Date.now()}`;
          currentAgentMsgIdRef.current = newId;
          const newMsg: LiveChatMessage = {
            id: newId,
            sender: 'agent',
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            text: textDelta,
            live: true,
          };
          setMessages((prev) => [...prev, newMsg]);
        } else {
          setMessages((prev) =>
            prev.map((m) => (m.id === msgId ? { ...m, text: m.text + textDelta } : m))
          );
        }
      },

      onTurnComplete: (fullText) => {
        const agentMsgId = currentAgentMsgIdRef.current;
        if (!agentMsgId) {
          if (fullText && fullText.trim()) {
            const newMsg: LiveChatMessage = {
              id: `agent-live-${Date.now()}`,
              sender: 'agent',
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
              text: fullText,
              live: true,
            };
            setMessages((prev) => [...prev, newMsg]);
          }
        } else if (fullText && fullText.trim()) {
          setMessages((prev) =>
            prev.map((m) => {
              if (m.id !== agentMsgId) return m;
              if (!m.text.trim()) {
                return { ...m, text: fullText };
              }
              return m;
            })
          );
        }
        // Spoken request (transcribed this turn): "prepare the field report for GK-129".
        if (currentUserMsgIdRef.current) fieldReportRef.current(lastUserTextRef.current);
        currentUserMsgIdRef.current = null;
        currentAgentMsgIdRef.current = null;
      },

      onToolCall: (ev: ToolCallEvent) => {
        let msgId = currentAgentMsgIdRef.current;
        if (!msgId) {
          msgId = `agent-live-${Date.now()}`;
          currentAgentMsgIdRef.current = msgId;
          const newMsg: LiveChatMessage = {
            id: msgId,
            sender: 'agent',
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            text: '',
            live: true,
            tools: [{ name: ev.name, status: ev.status, duration_ms: ev.duration_ms }],
          };
          setMessages((prev) => [...prev, newMsg]);
          return;
        }

        setMessages((prev) =>
          prev.map((m) => {
            if (m.id !== msgId) return m;
            const currentTools = m.tools || [];
            const existingIdx = currentTools.findIndex((t) => t.name === ev.name);
            let updatedTools: ToolCallInfo[];
            if (existingIdx !== -1) {
              updatedTools = currentTools.map((t, idx) =>
                idx === existingIdx
                  ? { ...t, status: ev.status, duration_ms: ev.duration_ms ?? t.duration_ms }
                  : t
              );
            } else {
              updatedTools = [
                ...currentTools,
                { name: ev.name, status: ev.status, duration_ms: ev.duration_ms },
              ];
            }
            return { ...m, tools: updatedTools };
          })
        );
      },

      onFallbackReply: (msg) => {
        const hasValidRec =
          msg.recommendation &&
          typeof msg.recommendation === 'object' &&
          'title' in (msg.recommendation as any);

        const rec = hasValidRec ? (msg.recommendation as SafeRecommendation) : undefined;
        if (rec) {
          setCurrentRecommendation(rec);
        }

        const fbArtifacts = (msg.artifacts ?? []) as ChatArtifactType[];
        const agentMsg: LiveChatMessage = {
          id: `agent-fallback-${Date.now()}`,
          sender: 'agent',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          text: msg.text,
          recommendation: rec,
          artifacts: fbArtifacts.length > 0 ? fbArtifacts : undefined,
          live: true,
        };
        setMessages((prev) => [...prev, agentMsg]);
        if (onAgentAction) {
          const explicit = isExplicitDetailRequest(lastUserTextRef.current);
          for (const act of (msg.actions ?? []) as ChatAction[]) {
            onAgentAction({ ...act, explicit, view: pickCanvasView(act.source_tool, lastUserTextRef.current) });
          }
        }
      },

      onError: (message) => {
        const errMessage: LiveChatMessage = {
          id: `agent-err-${Date.now()}`,
          sender: 'agent',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          text: `⚠️ ${message}`,
          live: true,
        };
        setMessages((prev) => [...prev, errMessage]);
      },

      onFirstAudio: (latencyMs) => {
        setFirstAudioLatency(latencyMs);
      },

      onAction: (kind, payload: any) => {
        if (!onAgentAction) return;
        const actionWellId: string | null =
          payload?.well_id ?? payload?.data?.well_id ?? payload?.data?.identity?.well_id ?? null;
        let targetScreen: ChatAction['screen'] | null = null;
        if (kind === 'field_history_chart') targetScreen = 'field_history';
        else if (kind === 'field_comparison') targetScreen = 'field_compare';
        else if (kind === 'health_buckets') targetScreen = 'field_health';
        else if (kind === 'priority_queue') targetScreen = 'priority';
        else if (
          ['well_profile', 'well_production_chart', 'nba', 'counterfactual', 'intervention_classification'].includes(kind) ||
          (kind === 'attribution_waterfall' && actionWellId)
        ) {
          targetScreen = 'well';
        }

        if (targetScreen) {
          onAgentAction({
            kind: 'navigate',
            screen: targetScreen,
            field: payload?.field ?? payload?.data?.field ?? field ?? null,
            well_id: actionWellId ?? well?.id ?? null,
            source_tool: kind,
            explicit: isExplicitDetailRequest(lastUserTextRef.current),
            view: pickCanvasView(kind, lastUserTextRef.current),
          });
        }
      },

      onInterrupted: () => {
        currentUserMsgIdRef.current = null;
        currentAgentMsgIdRef.current = null;
      },
    });
  }, [client, onAgentAction, field, screen, well?.id]);

  // Connect when Live mode is ON; disconnect on unmount and when Live mode is turned OFF
  useEffect(() => {
    if (isLiveMode) {
      client.connect({
        well_id: well?.id,
        field: field ?? undefined,
        screen: screen ?? undefined,
        language,
      });
    } else {
      client.disconnect();
    }
    return () => {
      client.disconnect();
    };
  }, [isLiveMode, client]);

  // When well?.id, field, or screen changes while Live is on: setContext without reconnecting
  const prevWellIdRef = useRef<string | null | undefined>(well?.id);
  useEffect(() => {
    if (prevWellIdRef.current !== well?.id) {
      prevWellIdRef.current = well?.id;
      currentUserMsgIdRef.current = null;
      currentAgentMsgIdRef.current = null;
      if (isLiveMode) {
        client.setContext({
          well_id: well?.id ?? undefined,
          field: field ?? undefined,
          screen: screen ?? undefined,
        });
      }
    }
  }, [well?.id, field, screen, isLiveMode, client]);

  // When language changes while Live is on: setContext({ language }) without reconnecting
  const prevLanguageRef = useRef<AgentLanguage>(language);
  useEffect(() => {
    if (prevLanguageRef.current !== language) {
      prevLanguageRef.current = language;
      if (isLiveMode) {
        client.setContext({ language });
      }
    }
  }, [language, isLiveMode, client]);

  // Clean up open mic and talking states when live mode is toggled off
  useEffect(() => {
    if (!isLiveMode) {
      setIsOpenMic(false);
      setIsTalking(false);
      isTalkingRef.current = false;
    }
  }, [isLiveMode]);

  // Load SpeechSynthesis voices cache (kept for text-mode authentic Indian English)
  useEffect(() => {
    const updateVoices = () => {
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        setVoices(window.speechSynthesis.getVoices());
      }
    };
    updateVoices();
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.onvoiceschanged = updateVoices;
    }
    return () => {
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        window.speechSynthesis.onvoiceschanged = null;
      }
    };
  }, []);

  // Cleanup speech on unmount
  useEffect(() => {
    return () => {
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  // Reset or initialize context whenever well, field, or language changes
  useEffect(() => {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    setLegacySpeaking(false);

    let greetingText = '';
    if (well) {
      if (language === 'hinglish') {
        greetingText = `Operational context loaded for **${well.name}** (${well.current_metrics.oil_bopd} BOPD, ${well.status.toUpperCase()}). Pichla workover, wax problem, ya recommendations ke baare mein puchhiye.`;
      } else if (language === 'hindi') {
        greetingText = `**${well.name}** की जानकारी उपलब्ध है (${well.current_metrics.oil_bopd} बीओपीडी, ${well.status})। आप वर्कओवर इतिहास या सुधार सिफारिशों के बारे में पूछ सकते हैं।`;
      } else {
        greetingText = `Live operational context loaded for **${well.name}** (${well.current_metrics.oil_bopd} BOPD, ${well.status.toUpperCase()}). Ask me what happened to this well, past workovers, or remediation steps.`;
      }
    } else if (field) {
      if (language === 'hinglish') {
        greetingText = `Operational context loaded for **${field}** field. Field production, health buckets, ya priority queue ke baare mein puchhiye.`;
      } else if (language === 'hindi') {
        greetingText = `**${field}** फील्ड की जानकारी उपलब्ध है। उत्पादन, हेल्थ बकेट्स या प्राथमिकता सूची के बारे में पूछ सकते हैं।`;
      } else {
        greetingText = `Operational context loaded for **${field}** field. Ask about field production history, health buckets, or priority candidates.`;
      }
    } else {
      if (language === 'hinglish') {
        greetingText = `WellPulse AI Agent ready for Assam Asset. Kisi bhi field ya well ke baare mein puchhiye.`;
      } else if (language === 'hindi') {
        greetingText = `असम एसेट ऑपरेशंस कोपायलट सक्रिय है। किसी भी फील्ड या वेल के बारे में पूछ सकते हैं।`;
      } else {
        greetingText = `WellPulse AI Agent ready for Assam Asset. Ask about any field, priority candidates, or select a wellhead.`;
      }
    }

    const greeting: LiveChatMessage = {
      id: `init-${well?.id || field || 'fleet'}-${Date.now()}`,
      sender: 'agent',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      text: greetingText,
    };

    setMessages([greeting]);
    setCurrentRecommendation(null);
  }, [well?.id, field, language]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isProcessing, voiceState]);

  // Helper to render bold markdown cleanly without breaking Devanagari ligatures
  const renderFormattedText = (text: string) => {
    const parts = text.split(/(\*\*.*?\*\*)/g);
    return parts.map((part, index) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return (
          <strong key={index} className="font-semibold text-white">
            {part.slice(2, -2)}
          </strong>
        );
      }
      return part;
    });
  };

  // Natural Speech Synthesis (TTS) - kept ONLY for text-mode replies and 'Replay Voice'
  const speakText = (text: string) => {
    if (isMuted || typeof window === 'undefined' || !('speechSynthesis' in window)) return;

    window.speechSynthesis.cancel();

    const cleanText = text
      .replace(/[*#_`]/g, '')
      .replace(/\[.*?\]/g, '')
      .replace(/\(.*?\)/g, '')
      .replace(/•/g, '')
      .replace(/🎙️.*$/g, '')
      .replace(/\s+/g, ' ')
      .trim();

    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = 0.95;
    utterance.pitch = 1.0;

    const availableVoices = voices.length > 0 ? voices : window.speechSynthesis.getVoices();
    let targetVoice: SpeechSynthesisVoice | undefined;

    if (language === 'hindi') {
      targetVoice = availableVoices.find(
        (v) =>
          v.lang === 'hi-IN' ||
          v.lang === 'hi_IN' ||
          v.name.toLowerCase().includes('hindi') ||
          v.name.toLowerCase().includes('kalpana') ||
          v.name.toLowerCase().includes('hemant')
      );
    }

    if (!targetVoice) {
      targetVoice = availableVoices.find(
        (v) =>
          v.lang === 'en-IN' ||
          v.lang === 'en_IN' ||
          v.name.toLowerCase().includes('india') ||
          v.name.toLowerCase().includes('neerja') ||
          v.name.toLowerCase().includes('prabhat') ||
          v.name.toLowerCase().includes('heera') ||
          v.name.toLowerCase().includes('ravi') ||
          v.name.toLowerCase().includes('veena') ||
          v.name.toLowerCase().includes('kiran') ||
          v.lang === 'hi-IN' ||
          v.lang === 'hi_IN'
      );
    }

    if (targetVoice) {
      utterance.voice = targetVoice;
      utterance.lang = targetVoice.lang;
    } else {
      utterance.lang = language === 'hindi' ? 'hi-IN' : 'en-IN';
    }

    utterance.onstart = () => setLegacySpeaking(true);
    utterance.onend = () => setLegacySpeaking(false);
    utterance.onerror = () => setLegacySpeaking(false);

    window.speechSynthesis.speak(utterance);
  };

  // Push-to-talk pointer handlers (Live mode)
  const handlePointerDown = async (e: React.PointerEvent) => {
    e.preventDefault();
    try {
      await audioPlayer.resume();
      await client.startTalking();
      isTalkingRef.current = true;
      setIsTalking(true);
    } catch (err) {
      console.warn('Microphone access failed:', err);
      alert(
        'Could not access microphone. Please allow microphone permissions in your browser or type your question below.'
      );
      isTalkingRef.current = false;
      setIsTalking(false);
    }
  };

  const handlePointerUp = () => {
    if (isTalkingRef.current) {
      client.stopTalking();
      isTalkingRef.current = false;
      setIsTalking(false);
    }
  };

  const handlePointerLeave = () => {
    if (isTalkingRef.current) {
      client.stopTalking();
      isTalkingRef.current = false;
      setIsTalking(false);
    }
  };

  // Push-to-talk Spacebar hold listener (Live mode, connected/resumed, open-mic OFF)
  useEffect(() => {
    if (!isLiveMode) return;
    const isLiveReady = liveStatus === 'connected' || liveStatus === 'resumed';
    if (!isLiveReady || isOpenMic) return;

    const handleKeyDown = async (e: KeyboardEvent) => {
      if (e.code !== 'Space' || e.repeat) return;
      const target = e.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.isContentEditable)
      ) {
        return;
      }
      e.preventDefault();
      try {
        await audioPlayer.resume();
        await client.startTalking();
        isTalkingRef.current = true;
        setIsTalking(true);
      } catch (err) {
        console.warn('Microphone access failed:', err);
        alert(
          'Could not access microphone. Please allow microphone permissions in your browser or type your question below.'
        );
        isTalkingRef.current = false;
        setIsTalking(false);
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.code !== 'Space') return;
      const target = e.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.isContentEditable)
      ) {
        return;
      }
      e.preventDefault();
      if (isTalkingRef.current) {
        client.stopTalking();
        isTalkingRef.current = false;
        setIsTalking(false);
      }
    };

    const handleWindowBlur = () => {
      if (isTalkingRef.current) {
        client.stopTalking();
        isTalkingRef.current = false;
        setIsTalking(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    window.addEventListener('blur', handleWindowBlur);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
      window.removeEventListener('blur', handleWindowBlur);
    };
  }, [isLiveMode, liveStatus, isOpenMic, client]);

  // Open-mic toggle handler (Live mode only)
  const toggleOpenMic = async () => {
    try {
      await audioPlayer.resume();
      const next = !isOpenMic;
      await client.setOpenMic(next);
      setIsOpenMic(next);
    } catch (err) {
      console.warn('Microphone access failed for open mic:', err);
      alert('Could not access microphone. Please allow microphone permissions.');
      setIsOpenMic(false);
    }
  };

  // Mute button handler: in Live mode, interrupts audio playback and signals the server
  const handleToggleMute = () => {
    if (legacySpeaking && typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      setLegacySpeaking(false);
    }
    if (isLiveMode) {
      // Mute in Live mode interrupts playing audio and sends interrupt signal to Gemini Live
      client.interrupt();
    }
    setIsMuted(!isMuted);
  };

  // Text message send path: uses POST /api/chat (ADK tool-grounded agent)
  const handleSendMessage = async (textToSend: string, fromVoice: boolean = false) => {
    if (!textToSend.trim() || isProcessing) return;
    lastUserTextRef.current = textToSend;

    const userMessage: LiveChatMessage = {
      id: `user-${Date.now()}`,
      sender: 'user',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      text: textToSend,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputPrompt('');
    maybeOpenFieldReport(textToSend);
    setIsProcessing(true);

    try {
      const reply = await postChat({
        message: textToSend,
        language,
        field: (field as any) || (well?.field as any) || null,
        well_id: well?.id ?? null,
        screen: screen ?? null,
      });

      const tools: ToolCallInfo[] = (reply.tool_calls || []).map((t) => ({
        name: t.name,
        status: t.status,
        duration_ms: t.duration_ms,
      }));

      const agentMessage: LiveChatMessage = {
        id: `agent-${Date.now()}`,
        sender: 'agent',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        text: reply.response,
        tools: tools.length > 0 ? tools : undefined,
        artifacts: reply.artifacts && reply.artifacts.length > 0 ? reply.artifacts : undefined,
        recommendation: reply.recommendation || undefined,
        status: reply.status,
      };

      setMessages((prev) => [...prev, agentMessage]);
      if (reply.recommendation) {
        setCurrentRecommendation(reply.recommendation);
      }

      if (reply.actions && reply.actions.length > 0 && onAgentAction) {
        const explicit = isExplicitDetailRequest(textToSend);
        for (const act of reply.actions) {
          onAgentAction({ ...act, explicit, view: pickCanvasView(act.source_tool, textToSend) });
        }
      }

      if (fromVoice && reply.response) {
        speakText(reply.response);
      }
    } catch (err) {
      console.error('Chat error:', err);
      const errorMessage: LiveChatMessage = {
        id: `err-${Date.now()}`,
        sender: 'agent',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        text: 'Connection error. Please ensure the backend service is running.',
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsProcessing(false);
    }
  };

  // High-level message submission (checks Live mode status)
  const submitMessage = async (customPrompt?: string) => {
    const textToSend = customPrompt || inputPrompt;
    if (!textToSend.trim()) return;

    const isLiveReady =
      isLiveMode && (liveStatus === 'connected' || liveStatus === 'resumed');

    if (isLiveReady) {
      const userMessage: LiveChatMessage = {
        id: `user-${Date.now()}`,
        sender: 'user',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        text: textToSend,
        live: true,
      };
      setMessages((prev) => [...prev, userMessage]);
      setInputPrompt('');
      lastUserTextRef.current = textToSend;
      const sent = client.sendText(textToSend);
      if (!sent) {
        // Fallback to HTTP if socket unexpectedly failed
        await handleSendMessage(textToSend, false);
      } else {
        maybeOpenFieldReport(textToSend);
      }
      return;
    }

    // When Live is OFF or status is fallback/disconnected/connecting:
    await handleSendMessage(textToSend, false);
  };

  // Language-Specific Suggested Prompts
  const suggestedPrompts =
    language === 'hinglish'
      ? well
        ? [
            'What happened to this well?',
            'Pichla workover kisne kiya tha?',
            'Water cut aur wax risk kya hai?',
            'Engineering recommendation batao',
          ]
        : [
            'Kaun se wells highest priority par hain?',
            'Lakwa vs Geleki field compare karo',
            'Underperforming wells ki health report dikhao',
            '5 year field production history batao',
          ]
      : language === 'hindi'
      ? well
        ? [
            'इस कुएं को क्या हुआ?',
            'पिछला वर्कओवर किसने किया था?',
            'वॉटर कट और स्केल का क्या खतरा है?',
            'सुधार की सिफारिश बताएं',
          ]
        : [
            'प्राथमिकता वाले कुओं की सूची दिखाएं',
            'फील्ड उत्पादन की तुलना करें',
            'एट-रिस्क कुओं की स्थिति बताएं',
            '5 साल का फील्ड इतिहास बताएं',
          ]
      : well
      ? [
          'What happened to this well?',
          'Why did this well trip / fail?',
          'Who supervised the last workover?',
          'Recommend engineering action',
        ]
      : [
          'Show high priority intervention candidates',
          'Compare Lakwa and Geleki performance',
          'Show health buckets and at-risk wells',
          '5-year field production history',
        ];

  // Derived state flags for Voice UI
  const isLiveReady = isLiveMode && (liveStatus === 'connected' || liveStatus === 'resumed');
  const activeListening = isLiveMode && voiceState === 'listening';
  const activeSpeaking = isLiveMode ? voiceState === 'speaking' : legacySpeaking;
  const activeThinking = isLiveMode ? voiceState === 'thinking' : isProcessing;

  // Let the floating launcher mirror voice state while the panel is minimised.
  useEffect(() => {
    onStatusChange?.({
      live: isLiveReady,
      listening: activeListening || isTalking,
      speaking: activeSpeaking,
      thinking: activeThinking,
    });
  }, [isLiveReady, activeListening, isTalking, activeSpeaking, activeThinking, onStatusChange]);

  return (
    <div className="flex flex-col h-full bg-surface">
      {/* Header — row 1: identity + controls (one state-aware Live button; no duplicate badges) */}
      <div className="border-b border-border px-3 pt-2 pb-1.5 shrink-0 bg-[#12161c]">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-7 h-7 rounded-md bg-accent/20 border border-accent/40 flex items-center justify-center shrink-0">
              <Bot className="w-4 h-4 text-accent" />
            </div>
            <h3 className="text-xs font-bold text-white font-sans truncate">WellPulse AI Agent</h3>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            {(() => {
              const st = !isLiveMode
                ? { label: 'Live off', cls: 'bg-[#0d1117] text-textMuted border-border hover:text-white', pulse: false }
                : liveStatus === 'connected' || liveStatus === 'resumed'
                ? { label: 'Live', cls: 'bg-emerald-950/70 text-emerald-300 border-emerald-700/60 font-semibold', pulse: true }
                : liveStatus === 'connecting' || liveStatus === 'reconnecting'
                ? { label: 'Connecting…', cls: 'bg-amber-950/60 text-amber-300 border-amber-700/60 animate-pulse', pulse: false }
                : { label: 'Text only', cls: 'bg-rose-950/60 text-rose-300 border-rose-700/60', pulse: false };
              const tip = !isLiveSupported()
                ? 'Live voice not supported in this browser'
                : isLiveMode
                ? `Live voice ${liveStatus}${statusInfo.model ? ` · ${statusInfo.model}` : ''}${
                    firstAudioLatency !== null ? ` · first audio ${Math.round(firstAudioLatency)} ms` : ''
                  } — click to switch to text`
                : 'Switch to live voice';
              return (
                <button
                  type="button"
                  onClick={() => setIsLiveMode((prev) => !prev)}
                  title={tip}
                  className={`flex items-center gap-1 px-2 py-1 rounded border text-[11px] font-sans transition-colors ${st.cls}`}
                >
                  <Radio className={`w-3.5 h-3.5 ${st.pulse ? 'animate-pulse' : ''}`} />
                  <span>{st.label}</span>
                </button>
              );
            })()}
            {isLiveMode && liveStatus === 'fallback' && (
              <button
                type="button"
                onClick={() => client.retry()}
                className="text-[10px] font-mono text-accent hover:text-white px-1"
                title="Retry live voice"
              >
                Retry
              </button>
            )}
            <button
              type="button"
              onClick={handleToggleMute}
              title={isMuted ? 'Unmute audio' : 'Mute audio'}
              className="p-1.5 rounded text-textMuted hover:text-white hover:bg-border transition-colors"
            >
              {isMuted ? <VolumeX className="w-4 h-4 text-rose-400" /> : <Volume2 className="w-4 h-4" />}
            </button>
            {headerActions}
          </div>
        </div>

        {/* Row 2: what the agent sees + language */}
        <div className="mt-1.5 flex items-center justify-between gap-2 text-[10px] font-mono">
          <div className="flex items-center gap-1 min-w-0 text-textMuted" title="Screen context sent with every question">
            <span>Context:</span>
            <span className="text-white truncate" data-testid="agent-context-chip">
              {contextLabel || 'Assam Asset'}
            </span>
          </div>
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value as AgentLanguage)}
            title="Agent language"
            aria-label="Agent language"
            className="bg-[#0d1117] border border-border rounded px-1 py-0.5 text-[10px] text-textMain focus:outline-none focus:border-accent"
          >
            <option value="hinglish">Hinglish</option>
            <option value="english">English</option>
            <option value="hindi">हिंदी</option>
          </select>
        </div>
      </div>

      {/* Dynamic Sound Wave Visualizer Banner (When Active) */}
      {(activeListening || activeSpeaking) && (
        <div
          className={`h-10 border-b px-4 flex items-center justify-between text-xs font-mono transition-colors ${
            activeListening
              ? 'bg-red-950/70 border-red-800/70'
              : 'bg-blue-950/40 border-blue-800/40'
          }`}
        >
          <span
            className={`flex items-center gap-2 font-medium ${
              activeListening ? 'text-red-300' : 'text-blue-300'
            }`}
          >
            {activeListening ? (
              isOpenMic ? (
                <>
                  <span className="w-2 h-2 rounded-full bg-red-500 animate-ping"></span>
                  <span>Listening (open mic)</span>
                </>
              ) : (
                <>
                  <span className="w-2 h-2 rounded-full bg-red-500 animate-ping"></span>
                  <span>🔴 Listening to voice... (Hold to talk)</span>
                </>
              )
            ) : (
              <>
                <Volume2 className="w-3.5 h-3.5 text-accent animate-pulse" />
                <span>{isLiveMode ? 'Agent speaking...' : 'Speaking diagnosis (Indian English)...'}</span>
              </>
            )}
          </span>

          {/* Animated Frequency Bars */}
          <div className="flex items-center gap-1 h-5">
            <div
              className={`w-1 rounded-full animate-wave ${activeListening ? 'bg-red-400' : 'bg-accent'}`}
              style={{ animationDelay: '0ms' }}
            ></div>
            <div
              className={`w-1 rounded-full animate-wave ${activeListening ? 'bg-red-400' : 'bg-accent'}`}
              style={{ animationDelay: '150ms' }}
            ></div>
            <div
              className={`w-1 rounded-full animate-wave ${activeListening ? 'bg-red-400' : 'bg-accent'}`}
              style={{ animationDelay: '300ms' }}
            ></div>
            <div
              className={`w-1 rounded-full animate-wave ${activeListening ? 'bg-red-400' : 'bg-accent'}`}
              style={{ animationDelay: '450ms' }}
            ></div>
            <div
              className={`w-1 rounded-full animate-wave ${activeListening ? 'bg-red-400' : 'bg-accent'}`}
              style={{ animationDelay: '200ms' }}
            ></div>
          </div>
        </div>
      )}

      {/* Chat Messages Stream */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 font-sans text-xs">
        {messages.map((msg) => msg.fieldReportWell ? (
          <div key={msg.id} className="flex pl-9">
            <button
              type="button"
              onClick={() => onOpenFieldReport?.(msg.fieldReportWell as string)}
              title="Re-open the printable field report"
              className="flex items-center gap-1.5 text-[11px] font-mono text-accent hover:text-white bg-accent/10 hover:bg-accent/25 border border-accent/40 rounded-full px-2.5 py-1 transition-colors"
            >
              <span aria-hidden>↗</span>
              <span>Field report · {msg.fieldReportWell}</span>
            </button>
          </div>
        ) : (
          <div
            key={msg.id}
            className={`flex gap-3 ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            {msg.sender === 'agent' && (
              <div className="w-6 h-6 rounded-full bg-accent/20 border border-accent/40 flex items-center justify-center shrink-0 mt-0.5">
                <Bot className="w-3.5 h-3.5 text-accent" />
              </div>
            )}

            <div className="max-w-[85%] space-y-2">
              <div
                className={`p-3 rounded-xl leading-relaxed ${
                  msg.sender === 'user'
                    ? 'bg-blue-600 text-white font-medium rounded-tr-none'
                    : 'bg-[#0d1117] text-textMain border border-border rounded-tl-none shadow-md'
                }`}
              >
                {/* Degraded model badge */}
                {msg.status === 'degraded' && (
                  <div className="mb-2 flex items-center gap-1.5 text-[10px] font-mono text-amber-300 bg-amber-950/40 border border-amber-700/50 px-2 py-0.5 rounded">
                    <AlertTriangle className="w-3 h-3 text-amber-400 shrink-0" />
                    <span>Model unavailable — showing tool output</span>
                  </div>
                )}

                {/* Tool call trace line inside agent bubble */}
                {msg.tools && msg.tools.length > 0 && (
                  <div className={`${msg.text ? 'mb-2' : ''} space-y-1`}>
                    {msg.tools.map((t, i) => (
                      <div
                        key={i}
                        className="flex items-center gap-1.5 text-[10px] font-mono text-textMuted bg-[#12161c] px-2 py-0.5 rounded border border-border/50"
                      >
                        <Wrench className="w-2.5 h-2.5 text-accent" />
                        <span className="font-semibold text-textMain">{t.name}</span>
                        <span>…</span>
                        <span
                          className={
                            t.status === 'done'
                              ? 'text-emerald-400'
                              : 'text-amber-400 animate-pulse'
                          }
                        >
                          {t.status}
                        </span>
                        {typeof t.duration_ms === 'number' && (
                          <span className="text-textMuted">{t.duration_ms} ms</span>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {msg.text ? (
                  <div className="whitespace-pre-line font-sans text-xs leading-relaxed tracking-normal">
                    {renderFormattedText(msg.text)}
                  </div>
                ) : null}

                {/* Artifacts rendered via ChatArtifact */}
                {msg.artifacts && msg.artifacts.length > 0 && (
                  <div className="mt-2 space-y-2">
                    {msg.artifacts.map((art, idx) => {
                      const target = PANEL_ARTIFACTS[art.kind];
                      if (target && onAgentAction) {
                        const d = art.data as Record<string, any> | null | undefined;
                        const artWell: string | null =
                          target.screen === 'well'
                            ? d?.well_id ?? (art.kind === 'well_profile' ? d?.id : null) ?? well?.id ?? null
                            : null;
                        if (target.screen !== 'well' || artWell) {
                          const prevUser = messages.slice(0, messages.indexOf(msg)).reverse().find((m) => m.sender === 'user')?.text;
                          const view = target.screen === 'well' ? pickCanvasView(art.kind, prevUser ?? '') : undefined;
                          const label = view ? VIEW_LABEL[view] ?? target.label : target.label;
                          return (
                            <button
                              key={idx}
                              type="button"
                              onClick={() =>
                                onAgentAction({
                                  kind: 'navigate',
                                  screen: target.screen,
                                  field: (d?.field as string | undefined) ?? field ?? null,
                                  well_id: artWell,
                                  source_tool: art.kind,
                                  explicit: true,
                                  view,
                                })
                              }
                              title="Open this view in the panel"
                              className="flex items-center gap-1.5 text-[11px] font-mono text-accent hover:text-white bg-accent/10 hover:bg-accent/25 border border-accent/40 rounded-full px-2.5 py-1 transition-colors"
                            >
                              <span aria-hidden>↗</span>
                              <span>
                                Showing in panel · {label}
                                {artWell ? ` · ${artWell}` : ''}
                              </span>
                            </button>
                          );
                        }
                      }
                      return (
                      <ChatArtifact
                        key={idx}
                        artifact={art}
                        onOpenFullView={
                          onAgentAction
                            ? (wellId) =>
                                onAgentAction({
                                  kind: 'navigate',
                                  screen: 'well',
                                  field: null,
                                  well_id: wellId,
                                  source_tool: art.kind,
                                  explicit: true,
                                  view: pickCanvasView(art.kind, ''),
                                })
                            : undefined
                        }
                      />
                      );
                    })}
                  </div>
                )}

                {/* Recommendation: compact line; full card, evidence and steps are in the panel */}
                {msg.recommendation && (
                  <div className="mt-2 pt-2 border-t border-border/60 flex items-center gap-2 flex-wrap">
                    <Wrench className="w-3.5 h-3.5 text-accent shrink-0" />
                    <span className="text-accent font-bold font-mono text-[11px]">{msg.recommendation.title}</span>
                    <span className="text-emerald-400 font-mono text-[10px]">
                      +{msg.recommendation.projected_flow_uplift_bopd} BOPD
                    </span>
                    <span
                      className={`text-[9px] font-mono px-1.5 py-0.5 rounded font-semibold uppercase border ${
                        msg.recommendation.urgency_badge === 'critical'
                          ? 'bg-rose-950/60 text-rose-300 border-rose-700/60'
                          : msg.recommendation.urgency_badge === 'warning'
                          ? 'bg-amber-950/60 text-amber-300 border-amber-700/60'
                          : 'bg-emerald-950/60 text-emerald-300 border-emerald-700/60'
                      }`}
                    >
                      {msg.recommendation.urgency}
                    </span>
                    {onAgentAction && well?.id && (
                      <button
                        type="button"
                        onClick={() =>
                          onAgentAction({
                            kind: 'navigate',
                            screen: 'well',
                            field: field ?? null,
                            well_id: well.id,
                            source_tool: 'nba',
                            explicit: true,
                            view: 'recommendation',
                          })
                        }
                        className="ml-auto text-[10px] font-mono text-accent hover:text-white"
                      >
                        ↗ Open in panel
                      </button>
                    )}
                  </div>
                )}
              </div>

              <div className="flex items-center justify-between text-[10px] font-mono text-textMuted px-1">
                <span>{msg.timestamp}</span>
                {msg.sender === 'agent' && !msg.live && (
                  <button
                    type="button"
                    onClick={() => speakText(msg.text)}
                    className="flex items-center gap-1 hover:text-accent transition-colors"
                  >
                    <Play className="w-2.5 h-2.5" /> Replay Voice
                  </button>
                )}
              </div>
            </div>

            {msg.sender === 'user' && (
              <div className="w-6 h-6 rounded-full bg-blue-900 border border-blue-700 flex items-center justify-center shrink-0 mt-0.5">
                <User className="w-3.5 h-3.5 text-blue-200" />
              </div>
            )}
          </div>
        ))}

        {activeThinking && (
          <div className="flex gap-3 items-center text-textMuted text-xs font-mono">
            <div className="w-6 h-6 rounded-full bg-accent/20 border border-accent/40 flex items-center justify-center">
              <Bot className="w-3.5 h-3.5 text-accent animate-spin" />
            </div>
            <span>Analyzing well telemetry in {language.toUpperCase()}...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Suggested Prompt Chips */}
      <div className="px-4 py-2 border-t border-border/60 bg-[#0d1117] flex items-center gap-1.5 overflow-x-auto no-scrollbar">
        {suggestedPrompts.map((prompt, idx) => (
          <button
            key={idx}
            type="button"
            onClick={() => submitMessage(prompt)}
            className="whitespace-nowrap bg-surface hover:bg-border/80 border border-border text-[11px] font-sans text-textMuted hover:text-white px-2.5 py-1 rounded-full transition-colors flex items-center gap-1"
          >
            <Sparkles className="w-2.5 h-2.5 text-accent" /> {prompt}
          </button>
        ))}
      </div>

      {/* Voice & Text Input Box */}
      <div className="p-3 border-t border-border bg-surface">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            submitMessage();
          }}
          className="flex flex-col gap-2"
        >
          {/* Text box — full width, grows with the message (Enter sends, Shift+Enter adds a line) */}
          <div className="relative">
            <textarea
              ref={composerRef}
              rows={2}
              value={inputPrompt}
              onChange={(e) => {
                setInputPrompt(e.target.value);
                const el = e.currentTarget;
                el.style.height = 'auto';
                el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  submitMessage();
                }
              }}
            placeholder={
              activeListening
                ? isOpenMic
                  ? 'Listening continuously (open mic)...'
                  : 'Listening to your voice... Release to send'
                : isLiveMode && isLiveReady
                ? language === 'hinglish'
                  ? 'Type, or hold Space to talk to the agent...'
                  : language === 'hindi'
                  ? 'टाइप करें या बोलने के लिए Space दबाए रखें...'
                  : 'Type, or hold Space to talk to the agent...'
                : !isLiveSupported()
                ? 'Voice unavailable in this browser — use text'
                : language === 'hinglish'
                ? 'Type in Hinglish or English...'
                : language === 'hindi'
                ? 'हिंदी में टाइप करें...'
                : 'Type well or field query...'
            }
            disabled={activeListening || (!isLiveMode && isProcessing)}
              className="w-full min-h-[56px] max-h-40 resize-none bg-[#0d1117] border border-border text-[13px] leading-snug pl-3 pr-12 py-2.5 rounded-lg text-white placeholder-textMuted focus:outline-none focus:border-accent font-sans"
            />
            <button
              type="submit"
              disabled={!inputPrompt.trim() || (!isLiveMode && isProcessing)}
              title="Send (Enter)"
              aria-label="Send"
              className="absolute right-2 bottom-2 p-2 rounded-md bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:hover:bg-blue-600 text-white transition-colors"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>

          {/* Voice controls row */}
          <div className="flex items-center gap-2 flex-wrap">
          {!isLiveSupported() ? (
            <button
              type="button"
              disabled
              title="Voice unavailable in this browser — use text"
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-[#0d1117] text-textMuted border border-border/50 font-mono text-xs opacity-50 shrink-0 cursor-not-allowed"
            >
              <MicOff className="w-4 h-4 text-textMuted" />
              <span className="hidden sm:inline">Voice unavailable</span>
            </button>
          ) : isLiveMode ? (
            isLiveReady ? (
              <>
                {/* Open mic toggle */}
                <button
                  type="button"
                  onClick={toggleOpenMic}
                  title={isOpenMic ? 'Disable open mic' : 'Enable continuous open mic (server VAD)'}
                  className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-mono font-medium transition-colors shrink-0 ${
                    isOpenMic
                      ? 'bg-red-950/80 text-red-300 border border-red-700 shadow-sm shadow-red-700/50'
                      : 'bg-[#0d1117] text-textMuted hover:text-white border border-border'
                  }`}
                >
                  {isOpenMic ? (
                    <MicOff className="w-3.5 h-3.5 text-red-400" />
                  ) : (
                    <Mic className="w-3.5 h-3.5 text-emerald-400" />
                  )}
                  <span>{isOpenMic ? 'Open mic on' : 'Open mic'}</span>
                </button>

                {/* Push-to-talk button: hidden when open mic is on */}
                {!isOpenMic && (
                  <button
                    type="button"
                    onPointerDown={handlePointerDown}
                    onPointerUp={handlePointerUp}
                    onPointerLeave={handlePointerLeave}
                    title="Hold to talk to the agent (or hold Spacebar)"
                    className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg font-mono text-xs font-semibold select-none transition-all shrink-0 ${
                      isTalking
                        ? 'bg-red-600 hover:bg-red-700 text-white border border-red-400 shadow-lg shadow-red-600/40 animate-pulse'
                        : 'bg-[#0d1117] text-emerald-400 hover:text-white hover:bg-emerald-600/30 border border-emerald-500/50'
                    }`}
                  >
                    <Mic className={`w-4 h-4 ${isTalking ? 'text-white' : 'text-emerald-400'}`} />
                    <span>{isTalking ? 'Listening...' : 'Hold to talk'}</span>
                  </button>
                )}
              </>
            ) : (
              <button
                type="button"
                disabled
                title={`Live voice ${liveStatus}`}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-[#0d1117] text-textMuted border border-border/50 font-mono text-xs opacity-50 shrink-0 cursor-not-allowed"
              >
                <Mic className="w-4 h-4 text-textMuted" />
                <span>{liveStatus === 'connecting' ? 'Connecting...' : 'Hold to talk'}</span>
              </button>
            )
          ) : null}
            <span className="ml-auto text-[10px] font-mono text-textMuted hidden min-[380px]:inline">
              Enter to send · Shift+Enter new line
            </span>
          </div>
        </form>
      </div>
    </div>
  );
};
