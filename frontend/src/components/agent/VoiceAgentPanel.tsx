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

interface VoiceAgentPanelProps {
  well: WellDetail;
}

type AgentLanguage = 'hinglish' | 'english' | 'hindi';

export interface ToolCallInfo {
  name: string;
  status: string;
  duration_ms?: number;
}

export interface SafeRecommendation extends Recommendation {
  estimated_cost_usd?: number;
  estimated_payback_days?: number;
}

export type LiveChatMessage = Omit<ChatMessage, 'recommendation'> & {
  tools?: ToolCallInfo[];
  live?: boolean;
  recommendation?: SafeRecommendation;
};

export const VoiceAgentPanel: React.FC<VoiceAgentPanelProps> = ({ well }) => {
  const [messages, setMessages] = useState<LiveChatMessage[]>([]);
  const [inputPrompt, setInputPrompt] = useState<string>('');
  const [language, setLanguage] = useState<AgentLanguage>('english');
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

  // Legacy fallback voice states (for text mode when Live mode is OFF)
  const [legacyListening, setLegacyListening] = useState<boolean>(false);
  const [legacyRecordingSeconds, setLegacyRecordingSeconds] = useState<number>(0);
  const [legacySpeaking, setLegacySpeaking] = useState<boolean>(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const isTalkingRef = useRef<boolean>(false);
  const currentUserMsgIdRef = useRef<string | null>(null);
  const currentAgentMsgIdRef = useRef<string | null>(null);

  // Legacy MediaRecorder refs
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerIntervalRef = useRef<any>(null);

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
            text: 'Gemini Live session resumed — conversation memory kept.',
            live: true,
          };
          setMessages((prev) => [...prev, resumeMsg]);
        } else if (s === 'fallback') {
          const fbText = info?.message
            ? `Gemini Live unavailable — switched to text (retry). (${info.message})`
            : 'Gemini Live unavailable — switched to text (retry).';
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

        const agentMsg: LiveChatMessage = {
          id: `agent-fallback-${Date.now()}`,
          sender: 'agent',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          text: msg.text,
          recommendation: rec,
          live: true,
        };
        setMessages((prev) => [...prev, agentMsg]);
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

      onInterrupted: () => {
        currentUserMsgIdRef.current = null;
        currentAgentMsgIdRef.current = null;
      },
    });
  }, [client]);

  // Connect when Live mode is ON; disconnect on unmount and when Live mode is turned OFF
  useEffect(() => {
    if (isLiveMode) {
      client.connect({ well_id: well.id, language });
    } else {
      client.disconnect();
    }
    return () => {
      client.disconnect();
    };
  }, [isLiveMode, client]);

  // When well.id changes while Live is on: setContext({ well_id: well.id }) without reconnecting
  const prevWellIdRef = useRef<string>(well.id);
  useEffect(() => {
    if (prevWellIdRef.current !== well.id) {
      prevWellIdRef.current = well.id;
      currentUserMsgIdRef.current = null;
      currentAgentMsgIdRef.current = null;
      if (isLiveMode) {
        client.setContext({ well_id: well.id });
      }
    }
  }, [well.id, isLiveMode, client]);

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

  // Cleanup legacy MediaRecorder, audio streams, and speech on unmount
  useEffect(() => {
    return () => {
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        try {
          mediaRecorderRef.current.stop();
        } catch (_) {}
      }
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      }
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  // Reset or initialize context whenever well or language changes
  useEffect(() => {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    setLegacySpeaking(false);

    let greetingText = '';
    if (language === 'hinglish') {
      greetingText = `Operational context loaded for **${well.name}** (${well.current_metrics.oil_bopd} BOPD, ${well.status.toUpperCase()}). Pichla workover, wax problem, ya recommendations ke baare mein puchhiye.`;
    } else if (language === 'hindi') {
      greetingText = `**${well.name}** की जानकारी उपलब्ध है (${well.current_metrics.oil_bopd} बीओपीडी, ${well.status})। आप वर्कओवर इतिहास या सुधार सिफारिशों के बारे में पूछ सकते हैं।`;
    } else {
      greetingText = `Live operational context loaded for **${well.name}** (${well.current_metrics.oil_bopd} BOPD, ${well.status.toUpperCase()}). Ask me what happened to this well, past workovers, or remediation steps.`;
    }

    const greeting: LiveChatMessage = {
      id: `init-${well.id}-${Date.now()}`,
      sender: 'agent',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      text: greetingText,
    };

    setMessages([greeting]);
    setCurrentRecommendation(null);
  }, [well.id, language]);

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

  // Legacy MediaRecorder functions (ONLY when Live mode is OFF)
  const startAudioRecording = async () => {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    setLegacySpeaking(false);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;
      audioChunksRef.current = [];

      let mimeType = 'audio/webm';
      if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
        mimeType = 'audio/webm;codecs=opus';
      } else if (MediaRecorder.isTypeSupported('audio/webm')) {
        mimeType = 'audio/webm';
      } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
        mimeType = 'audio/mp4';
      }

      const recorder = new MediaRecorder(stream, { mimeType });

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onstop = async () => {
        const recordedMime = recorder.mimeType || mimeType;
        const audioBlob = new Blob(audioChunksRef.current, { type: recordedMime });

        if (mediaStreamRef.current) {
          mediaStreamRef.current.getTracks().forEach((track) => track.stop());
          mediaStreamRef.current = null;
        }

        if (audioBlob.size > 0) {
          await sendAudioToGemini(audioBlob, recordedMime);
        }
      };

      mediaRecorderRef.current = recorder;
      recorder.start(250);
      setLegacyListening(true);
      setLegacyRecordingSeconds(0);

      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = setInterval(() => {
        setLegacyRecordingSeconds((prev) => prev + 1);
      }, 1000);
    } catch (err: any) {
      console.warn('Microphone access failed:', err);
      alert('Could not access microphone. Please allow microphone permissions in your browser or type your question below.');
      setLegacyListening(false);
    }
  };

  const stopAudioRecording = () => {
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
    }

    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try {
        mediaRecorderRef.current.stop();
      } catch (e) {
        console.warn('Recorder stop error:', e);
      }
    }
    setLegacyListening(false);
  };

  const sendAudioToGemini = async (audioBlob: Blob, mimeType: string) => {
    setIsProcessing(true);

    try {
      const base64Data = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => {
          const res = reader.result as string;
          const base64 = res.split(',')[1];
          resolve(base64);
        };
        reader.onerror = reject;
        reader.readAsDataURL(audioBlob);
      });

      const response = await fetch(`/api/wells/${well.id}/audio`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          audio_base64: base64Data,
          mime_type: mimeType,
          language: language,
        }),
      });

      if (!response.ok) {
        throw new Error(`Server returned HTTP ${response.status}`);
      }

      const data = await response.json();

      const userMessage: LiveChatMessage = {
        id: `user-${Date.now()}`,
        sender: 'user',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        text: `🎙️ ${data.user_transcript || 'Voice query'}`,
      };

      const agentMessage: LiveChatMessage = {
        id: `agent-${Date.now()}`,
        sender: 'agent',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        text: data.response,
        recommendation: data.recommendation || undefined,
      };

      setMessages((prev) => [...prev, userMessage, agentMessage]);
      if (data.recommendation) {
        setCurrentRecommendation(data.recommendation);
      }

      speakText(data.response);
    } catch (err) {
      console.error('Gemini audio processing error:', err);
      const errorMessage: LiveChatMessage = {
        id: `err-${Date.now()}`,
        sender: 'agent',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        text: 'Failed to process voice query. Please try again or type your question.',
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsProcessing(false);
    }
  };

  // Text message send path: uses POST /api/wells/{id}/chat when Live mode is OFF or not connected/resumed
  const handleSendMessage = async (textToSend: string, fromVoice: boolean = false) => {
    if (!textToSend.trim() || isProcessing) return;

    const userMessage: LiveChatMessage = {
      id: `user-${Date.now()}`,
      sender: 'user',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      text: textToSend,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputPrompt('');
    setIsProcessing(true);

    try {
      const response = await fetch(`/api/wells/${well.id}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: textToSend, language: language }),
      });

      const data = await response.json();

      const agentMessage: LiveChatMessage = {
        id: `agent-${Date.now()}`,
        sender: 'agent',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        text: data.response,
        recommendation: data.recommendation || undefined,
      };

      setMessages((prev) => [...prev, agentMessage]);
      if (data.recommendation) {
        setCurrentRecommendation(data.recommendation);
      }

      if (fromVoice) {
        speakText(data.response);
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
      const sent = client.sendText(textToSend);
      if (!sent) {
        // Fallback to HTTP if socket unexpectedly failed
        await handleSendMessage(textToSend, false);
      }
      return;
    }

    // When Live is OFF or status is fallback/disconnected/connecting:
    await handleSendMessage(textToSend, false);
  };

  // Language-Specific Suggested Prompts
  const suggestedPrompts =
    language === 'hinglish'
      ? [
          'What happened to this well?',
          'Pichla workover kisne kiya tha?',
          'Water cut aur wax risk kya hai?',
          'Engineering recommendation batao',
        ]
      : language === 'hindi'
      ? [
          'इस कुएं को क्या हुआ?',
          'पिछला वर्कओवर किसने किया था?',
          'वॉटर कट और स्केल का क्या खतरा है?',
          'सुधार की सिफारिश बताएं',
        ]
      : [
          'What happened to this well?',
          'Why did this well trip / fail?',
          'Who supervised the last workover?',
          'Recommend engineering action',
        ];

  // Derived state flags for Voice UI
  const isLiveReady = isLiveMode && (liveStatus === 'connected' || liveStatus === 'resumed');
  const activeListening = isLiveMode ? voiceState === 'listening' : legacyListening;
  const activeSpeaking = isLiveMode ? voiceState === 'speaking' : legacySpeaking;
  const activeThinking = isLiveMode ? voiceState === 'thinking' : isProcessing;

  const renderStatusBadge = () => {
    if (!isLiveMode) {
      return (
        <span className="text-[9px] font-mono text-textMuted bg-[#0d1117] px-1.5 py-0.5 rounded border border-border font-semibold">
          TEXT
        </span>
      );
    }

    switch (liveStatus) {
      case 'connecting':
        return (
          <span className="flex items-center gap-1 text-[9px] font-mono text-amber-400 bg-amber-950/60 px-1.5 py-0.5 rounded border border-amber-700/60 font-semibold animate-pulse">
            CONNECTING
          </span>
        );
      case 'connected':
      case 'resumed':
        return (
          <span
            title={statusInfo.model ? `Model: ${statusInfo.model}` : 'Gemini Live Connected'}
            className="flex items-center gap-1 text-[9px] font-mono text-emerald-400 bg-emerald-950/60 px-1.5 py-0.5 rounded border border-emerald-700/60 font-semibold cursor-help"
          >
            <Zap className="w-2.5 h-2.5 text-emerald-400" /> LIVE
          </span>
        );
      case 'reconnecting':
        return (
          <span className="flex items-center gap-1 text-[9px] font-mono text-amber-400 bg-amber-950/60 px-1.5 py-0.5 rounded border border-amber-700/60 font-semibold animate-pulse">
            RECONNECTING
          </span>
        );
      case 'fallback':
        return (
          <span className="flex items-center gap-1">
            <span className="text-[9px] font-mono text-rose-300 bg-rose-950/60 px-1.5 py-0.5 rounded border border-rose-700/60 font-semibold">
              TEXT MODE
            </span>
            <button
              type="button"
              onClick={() => client.retry()}
              className="text-[9px] font-mono text-accent hover:underline bg-[#0d1117] px-1.5 py-0.5 rounded border border-border transition-colors hover:text-white"
            >
              Retry Live
            </button>
          </span>
        );
      case 'disconnected':
      default:
        return (
          <span className="text-[9px] font-mono text-textMuted bg-[#0d1117] px-1.5 py-0.5 rounded border border-border font-semibold">
            TEXT
          </span>
        );
    }
  };

  return (
    <div className="flex flex-col h-full bg-surface border-l border-border">
      {/* Header */}
      <div className="h-14 border-b border-border px-3.5 flex items-center justify-between shrink-0 bg-[#12161c]">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md bg-accent/20 border border-accent/40 flex items-center justify-center">
            <Bot className="w-4 h-4 text-accent" />
          </div>
          <div>
            <h3 className="text-xs font-bold text-white font-sans flex items-center gap-1.5">
              WellPulse Copilot
              {renderStatusBadge()}
            </h3>
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] font-mono text-textMuted">
                {isLiveMode ? 'Gemini Live Voice Engine' : 'Standard Copilot'}
              </span>
              {isLiveMode && firstAudioLatency !== null && (
                <span className="text-[9px] font-mono text-emerald-400 bg-[#0d1117] px-1 py-0.2 rounded border border-border/50">
                  1st audio {Math.round(firstAudioLatency)} ms
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Live Mode Toggle, Language Selector & Audio Mute Controls */}
        <div className="flex items-center gap-2">
          {/* Mode Toggle Button */}
          <button
            type="button"
            onClick={() => setIsLiveMode((prev) => !prev)}
            title={
              !isLiveSupported()
                ? 'Gemini Live not supported in this browser'
                : isLiveMode
                ? 'Switch to Text Mode'
                : 'Switch to Gemini Live'
            }
            className={`flex items-center gap-1 px-2 py-1 rounded text-[11px] font-sans transition-colors ${
              isLiveMode
                ? 'bg-emerald-950/70 text-emerald-300 border border-emerald-700/60 font-semibold'
                : 'bg-[#0d1117] text-textMuted border border-border hover:text-white'
            }`}
          >
            <Radio className={`w-3.5 h-3.5 ${isLiveMode ? 'text-emerald-400 animate-pulse' : 'text-textMuted'}`} />
            <span>Live</span>
          </button>

          {/* Language Switcher */}
          <div className="flex items-center bg-[#0d1117] border border-border rounded-md p-0.5 text-[11px] font-sans">
            <button
              type="button"
              onClick={() => setLanguage('hinglish')}
              title="Hinglish (Hindi + English)"
              className={`px-1.5 py-0.5 rounded transition-colors ${
                language === 'hinglish'
                  ? 'bg-accent/20 text-accent font-bold'
                  : 'text-textMuted hover:text-white'
              }`}
            >
              🇮🇳 Hinglish
            </button>
            <button
              type="button"
              onClick={() => setLanguage('english')}
              title="English (Concise)"
              className={`px-1.5 py-0.5 rounded transition-colors ${
                language === 'english'
                  ? 'bg-blue-900/60 text-blue-300 font-bold'
                  : 'text-textMuted hover:text-white'
              }`}
            >
              🇬🇧 Eng
            </button>
            <button
              type="button"
              onClick={() => setLanguage('hindi')}
              title="Hindi (हिंदी)"
              className={`px-1.5 py-0.5 rounded transition-colors ${
                language === 'hindi'
                  ? 'bg-amber-900/60 text-amber-300 font-bold'
                  : 'text-textMuted hover:text-white'
              }`}
            >
              🇮🇳 हिंदी
            </button>
          </div>

          {/* Speaking Indicator */}
          {activeSpeaking && (
            <div className="flex items-center gap-1 text-[10px] font-mono text-accent animate-pulse">
              <span className="w-1.5 h-1.5 rounded-full bg-accent"></span> Speaking
            </div>
          )}

          {/* Audio Mute Toggle */}
          <button
            type="button"
            onClick={handleToggleMute}
            title={isMuted ? 'Unmute Audio' : 'Mute Audio'}
            className="p-1.5 rounded text-textMuted hover:text-white hover:bg-border transition-colors"
          >
            {isMuted ? <VolumeX className="w-4 h-4 text-rose-400" /> : <Volume2 className="w-4 h-4" />}
          </button>
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
              isLiveMode ? (
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
                  <span className="w-2 h-2 rounded-full bg-red-500 animate-ping"></span>
                  <span>🔴 Recording voice ({legacyRecordingSeconds}s)... Click Stop when done</span>
                </>
              )
            ) : (
              <>
                <Volume2 className="w-3.5 h-3.5 text-accent animate-pulse" />
                <span>{isLiveMode ? 'Gemini Live speaking...' : 'Speaking diagnosis (Indian English)...'}</span>
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
        {messages.map((msg) => (
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

                {/* Structured Recommendation in-line card */}
                {msg.recommendation && (
                  <div className="mt-3 pt-3 border-t border-border/80 space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5 text-accent font-bold font-mono text-[11px]">
                        <Wrench className="w-3.5 h-3.5" />
                        {msg.recommendation.title}
                      </div>
                      <span
                        className={`text-[9px] font-mono px-2 py-0.5 rounded font-semibold uppercase border ${
                          msg.recommendation.urgency_badge === 'critical'
                            ? 'bg-rose-950/60 text-rose-300 border-rose-700/60'
                            : msg.recommendation.urgency_badge === 'warning'
                            ? 'bg-amber-950/60 text-amber-300 border-amber-700/60'
                            : 'bg-emerald-950/60 text-emerald-300 border-emerald-700/60'
                        }`}
                      >
                        {msg.recommendation.urgency}
                      </span>
                    </div>

                    <div className="grid grid-cols-3 gap-2 bg-surface/60 p-2 rounded border border-border/60 font-mono text-[10px]">
                      {typeof msg.recommendation.estimated_cost_usd === 'number' && (
                        <div>
                          <span className="text-textMuted">Est. Cost:</span>
                          <div className="font-bold text-white">
                            ${msg.recommendation.estimated_cost_usd.toLocaleString()}
                          </div>
                        </div>
                      )}
                      <div>
                        <span className="text-textMuted">Uplift:</span>
                        <div className="font-bold text-emerald-400">
                          +{msg.recommendation.projected_flow_uplift_bopd} BOPD
                        </div>
                      </div>
                      {typeof msg.recommendation.estimated_payback_days === 'number' && (
                        <div>
                          <span className="text-textMuted">Payback:</span>
                          <div className="font-bold text-sky-400">
                            ~{msg.recommendation.estimated_payback_days} Days
                          </div>
                        </div>
                      )}
                    </div>

                    {msg.recommendation.action_items && msg.recommendation.action_items.length > 0 && (
                      <div className="space-y-1 text-[11px]">
                        <span className="text-textMuted font-mono text-[10px] uppercase font-bold">
                          Action Items:
                        </span>
                        <ul className="list-disc pl-4 space-y-0.5 text-textMain/90">
                          {msg.recommendation.action_items.map((item, i) => (
                            <li key={i}>{item}</li>
                          ))}
                        </ul>
                      </div>
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
          className="flex items-center gap-2"
        >
          {isLiveMode ? (
            isLiveReady ? (
              <>
                {/* Open mic toggle */}
                <button
                  type="button"
                  onClick={toggleOpenMic}
                  title={isOpenMic ? 'Disable open mic' : 'Enable continuous open mic (server VAD)'}
                  className={`flex items-center gap-1 px-2.5 py-2.5 rounded-lg text-xs font-mono font-medium transition-colors shrink-0 ${
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
                    title="Hold to talk with Gemini Live (or hold Spacebar)"
                    className={`flex items-center gap-1.5 px-3 py-2.5 rounded-lg font-mono text-xs font-semibold select-none transition-all shrink-0 ${
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
                title={`Gemini Live ${liveStatus}`}
                className="flex items-center gap-1.5 px-3 py-2.5 rounded-lg bg-[#0d1117] text-textMuted border border-border/50 font-mono text-xs opacity-50 shrink-0 cursor-not-allowed"
              >
                <Mic className="w-4 h-4 text-textMuted" />
                <span>Hold to talk</span>
              </button>
            )
          ) : (
            /* Legacy Voice Button when Live mode is OFF */
            legacyListening ? (
              <button
                type="button"
                onClick={stopAudioRecording}
                title="Click to stop recording"
                className="flex items-center gap-1.5 px-3 py-2.5 rounded-lg bg-red-600 hover:bg-red-700 text-white border border-red-400 font-mono text-xs font-semibold shadow-lg shadow-red-600/40 animate-pulse transition-all shrink-0"
              >
                <Square className="w-3.5 h-3.5 fill-current" />
                <span>Stop ({legacyRecordingSeconds}s)</span>
              </button>
            ) : (
              <button
                type="button"
                onClick={startAudioRecording}
                disabled={isProcessing}
                title="Click to record voice"
                className="flex items-center gap-1.5 px-3 py-2.5 rounded-lg bg-[#0d1117] text-emerald-400 hover:text-white hover:bg-emerald-600/30 border border-emerald-500/50 hover:border-emerald-400 font-mono text-xs font-medium transition-all shrink-0 disabled:opacity-40"
              >
                <Mic className="w-4 h-4 text-emerald-400" />
                <span>Voice</span>
              </button>
            )
          )}

          <input
            type="text"
            value={inputPrompt}
            onChange={(e) => setInputPrompt(e.target.value)}
            placeholder={
              activeListening
                ? isLiveMode
                  ? isOpenMic
                    ? 'Listening continuously (open mic)...'
                    : 'Listening to your voice... Release to send'
                  : `Recording voice in ${language.toUpperCase()}... Click Stop & Send when done`
                : isLiveMode && isLiveReady
                ? language === 'hinglish'
                  ? 'Type or hold Space to talk with Gemini Live...'
                  : language === 'hindi'
                  ? 'टाइप करें या बोलने के लिए Space दबाए रखें...'
                  : 'Type or hold Space to talk with Gemini Live...'
                : language === 'hinglish'
                ? 'Type in Hinglish or English... (or click Voice to speak)'
                : language === 'hindi'
                ? 'हिंदी में टाइप करें... (या बोलने के लिए Voice दबाएं)'
                : 'Type well query for text response... (or click Voice to speak)'
            }
            disabled={activeListening || (!isLiveMode && isProcessing)}
            className="flex-1 bg-[#0d1117] border border-border text-xs px-3 py-2.5 rounded-lg text-white placeholder-textMuted focus:outline-none focus:border-accent font-sans"
          />

          <button
            type="submit"
            disabled={!inputPrompt.trim() || (!isLiveMode && isProcessing)}
            className="p-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:hover:bg-blue-600 text-white transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
};
