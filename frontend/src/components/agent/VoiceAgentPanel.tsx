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
  Languages,
  Zap,
  Square,
} from 'lucide-react';
import { ChatMessage, Recommendation, WellDetail } from '../../types/well';

interface VoiceAgentPanelProps {
  well: WellDetail;
}

type AgentLanguage = 'hinglish' | 'english' | 'hindi';

export const VoiceAgentPanel: React.FC<VoiceAgentPanelProps> = ({ well }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputPrompt, setInputPrompt] = useState<string>('');
  const [isListening, setIsListening] = useState<boolean>(false);
  const [recordingSeconds, setRecordingSeconds] = useState<number>(0);
  const [isSpeaking, setIsSpeaking] = useState<boolean>(false);
  const [isMuted, setIsMuted] = useState<boolean>(false);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [language, setLanguage] = useState<AgentLanguage>('english');
  const [isLiveConnected, setIsLiveConnected] = useState<boolean>(false);
  const [currentRecommendation, setCurrentRecommendation] = useState<Recommendation | null>(null);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const lastInputWasVoiceRef = useRef<boolean>(false);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerIntervalRef = useRef<any>(null);

  // Initialize Gemini Live WebSocket
  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/wells/${well.id}/live`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setIsLiveConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'response') {
          const agentMessage: ChatMessage = {
            id: `agent-${Date.now()}`,
            sender: 'agent',
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            text: data.text,
            recommendation: data.recommendation || undefined,
          };
          setMessages((prev) => [...prev, agentMessage]);
          if (data.recommendation) {
            setCurrentRecommendation(data.recommendation);
          }
          setIsProcessing(false);
          // Only speak if user prompted via voice
          if (lastInputWasVoiceRef.current) {
            speakText(data.text);
          }
        } else if (data.type === 'thinking') {
          setIsProcessing(true);
        }
      } catch (err) {
        console.warn('Live WebSocket message parse error:', err);
      }
    };

    ws.onerror = (err) => {
      console.warn('Live WebSocket error, falling back to HTTP:', err);
      setIsLiveConnected(false);
    };

    ws.onclose = () => {
      setIsLiveConnected(false);
    };

    wsRef.current = ws;

    return () => {
      ws.close();
    };
  }, [well.id]);

  // Load SpeechSynthesis voices cache (for authentic Indian English en-IN)
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

  // Cleanup MediaRecorder, audio streams, and speech on unmount
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
      window.speechSynthesis.cancel();
    };
  }, []);

  // Reset or initialize context whenever well or language changes
  useEffect(() => {
    window.speechSynthesis.cancel();
    setIsSpeaking(false);

    let greetingText = '';
    if (language === 'hinglish') {
      greetingText = `Operational context loaded for **${well.name}** (${well.current_metrics.oil_bopd} BOPD, ${well.status.toUpperCase()}). Pichla workover, wax problem, ya recommendations ke baare mein puchhiye.`;
    } else if (language === 'hindi') {
      greetingText = `**${well.name}** की जानकारी उपलब्ध है (${well.current_metrics.oil_bopd} बीओपीडी, ${well.status})। आप वर्कओवर इतिहास या सुधार सिफारिशों के बारे में पूछ सकते हैं।`;
    } else {
      greetingText = `Live operational context loaded for **${well.name}** (${well.current_metrics.oil_bopd} BOPD, ${well.status.toUpperCase()}). Ask me what happened to this well, past workovers, or remediation steps.`;
    }

    const greeting: ChatMessage = {
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
  }, [messages, isProcessing]);

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

  // Natural Speech Synthesis (TTS) - Supports Authentic Indian English & Hindi Accents
  const speakText = (text: string) => {
    if (isMuted || !('speechSynthesis' in window)) return;

    window.speechSynthesis.cancel();

    // Clean text thoroughly for human speech cadence
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

    // Pick authentic Indian English (en-IN) or Hindi (hi-IN) voice
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

    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);

    window.speechSynthesis.speak(utterance);
  };

  const startAudioRecording = async () => {
    window.speechSynthesis.cancel();
    setIsSpeaking(false);

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
      setIsListening(true);
      setRecordingSeconds(0);

      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = setInterval(() => {
        setRecordingSeconds((prev) => prev + 1);
      }, 1000);
    } catch (err: any) {
      console.warn('Microphone access failed:', err);
      alert('Could not access microphone. Please allow microphone permissions in your browser or type your question below.');
      setIsListening(false);
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
    setIsListening(false);
  };

  const sendAudioToGemini = async (audioBlob: Blob, mimeType: string) => {
    setIsProcessing(true);
    lastInputWasVoiceRef.current = true;

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

      const userMessage: ChatMessage = {
        id: `user-${Date.now()}`,
        sender: 'user',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        text: `🎙️ ${data.user_transcript || 'Voice query'}`,
      };

      const agentMessage: ChatMessage = {
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

      // Voice prompt gets voice response back aloud in authentic Indian English
      speakText(data.response);
    } catch (err) {
      console.error('Gemini audio processing error:', err);
      const errorMessage: ChatMessage = {
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

  const handleSendMessage = async (customPrompt?: string, fromVoice: boolean = false) => {
    lastInputWasVoiceRef.current = fromVoice;
    const textToSend = customPrompt || inputPrompt;
    if (!textToSend.trim() || isProcessing) return;

    const userMessage: ChatMessage = {
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

      const agentMessage: ChatMessage = {
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

      // Voice responses ONLY if prompted by voice
      if (fromVoice) {
        speakText(data.response);
      }
    } catch (err) {
      console.error('Chat error:', err);
      const errorMessage: ChatMessage = {
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
              {isLiveConnected ? (
                <span className="flex items-center gap-1 text-[9px] font-mono text-emerald-400 bg-emerald-950/60 px-1.5 py-0.2 rounded border border-emerald-700/60 font-semibold">
                  <Zap className="w-2.5 h-2.5 text-emerald-400" /> LIVE
                </span>
              ) : (
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
              )}
            </h3>
            <span className="text-[10px] font-mono text-textMuted">Gemini Live Voice Engine</span>
          </div>
        </div>

        {/* Language Selector & Audio Mute Controls */}
        <div className="flex items-center gap-2">
          {/* Language Switcher */}
          <div className="flex items-center bg-[#0d1117] border border-border rounded-md p-0.5 text-[11px] font-sans">
            <button
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
          {isSpeaking && (
            <div className="flex items-center gap-1 text-[10px] font-mono text-accent animate-pulse">
              <span className="w-1.5 h-1.5 rounded-full bg-accent"></span> Speaking
            </div>
          )}

          {/* Audio Mute Toggle */}
          <button
            onClick={() => {
              if (isSpeaking) window.speechSynthesis.cancel();
              setIsMuted(!isMuted);
            }}
            title={isMuted ? 'Unmute Voice Playback' : 'Mute Voice Playback'}
            className="p-1.5 rounded text-textMuted hover:text-white hover:bg-border transition-colors"
          >
            {isMuted ? <VolumeX className="w-4 h-4 text-rose-400" /> : <Volume2 className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Dynamic Sound Wave Visualizer Banner (When Active) */}
      {(isListening || isSpeaking) && (
        <div
          className={`h-10 border-b px-4 flex items-center justify-between text-xs font-mono transition-colors ${
            isListening
              ? 'bg-red-950/70 border-red-800/70'
              : 'bg-blue-950/40 border-blue-800/40'
          }`}
        >
          <span
            className={`flex items-center gap-2 font-medium ${
              isListening ? 'text-red-300' : 'text-blue-300'
            }`}
          >
            {isListening ? (
              <>
                <span className="w-2 h-2 rounded-full bg-red-500 animate-ping"></span>
                <span>🔴 Recording voice for Gemini Live ({recordingSeconds}s)... Click Stop when done</span>
              </>
            ) : (
              <>
                <Volume2 className="w-3.5 h-3.5 text-accent animate-pulse" /> Speaking diagnosis (Indian English)...
              </>
            )}
          </span>

          {/* Animated Frequency Bars */}
          <div className="flex items-center gap-1 h-5">
            <div
              className={`w-1 rounded-full animate-wave ${isListening ? 'bg-red-400' : 'bg-accent'}`}
              style={{ animationDelay: '0ms' }}
            ></div>
            <div
              className={`w-1 rounded-full animate-wave ${isListening ? 'bg-red-400' : 'bg-accent'}`}
              style={{ animationDelay: '150ms' }}
            ></div>
            <div
              className={`w-1 rounded-full animate-wave ${isListening ? 'bg-red-400' : 'bg-accent'}`}
              style={{ animationDelay: '300ms' }}
            ></div>
            <div
              className={`w-1 rounded-full animate-wave ${isListening ? 'bg-red-400' : 'bg-accent'}`}
              style={{ animationDelay: '450ms' }}
            ></div>
            <div
              className={`w-1 rounded-full animate-wave ${isListening ? 'bg-red-400' : 'bg-accent'}`}
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
                <div className="whitespace-pre-line font-sans text-xs leading-relaxed tracking-normal">
                  {renderFormattedText(msg.text)}
                </div>

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
                      <div>
                        <span className="text-textMuted">Est. Cost:</span>
                        <div className="font-bold text-white">
                          ${msg.recommendation.estimated_cost_usd.toLocaleString()}
                        </div>
                      </div>
                      <div>
                        <span className="text-textMuted">Uplift:</span>
                        <div className="font-bold text-emerald-400">
                          +{msg.recommendation.projected_flow_uplift_bopd} BOPD
                        </div>
                      </div>
                      <div>
                        <span className="text-textMuted">Payback:</span>
                        <div className="font-bold text-sky-400">
                          ~{msg.recommendation.estimated_payback_days} Days
                        </div>
                      </div>
                    </div>

                    <div className="space-y-1 text-[11px]">
                      <span className="text-textMuted font-mono text-[10px] uppercase font-bold">Action Items:</span>
                      <ul className="list-disc pl-4 space-y-0.5 text-textMain/90">
                        {msg.recommendation.action_items.map((item, i) => (
                          <li key={i}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}
              </div>

              <div className="flex items-center justify-between text-[10px] font-mono text-textMuted px-1">
                <span>{msg.timestamp}</span>
                {msg.sender === 'agent' && (
                  <button
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

        {isProcessing && (
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
            onClick={() => handleSendMessage(prompt, false)}
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
            handleSendMessage(undefined, false);
          }}
          className="flex items-center gap-2"
        >
          {/* Voice Microphone Record Button */}
          {isListening ? (
            <button
              type="button"
              onClick={stopAudioRecording}
              title="Click to stop recording and send to Gemini Live"
              className="flex items-center gap-1.5 px-3 py-2.5 rounded-lg bg-red-600 hover:bg-red-700 text-white border border-red-400 font-mono text-xs font-semibold shadow-lg shadow-red-600/40 animate-pulse transition-all shrink-0"
            >
              <Square className="w-3.5 h-3.5 fill-current" />
              <span>Stop ({recordingSeconds}s)</span>
            </button>
          ) : (
            <button
              type="button"
              onClick={startAudioRecording}
              disabled={isProcessing}
              title="Click to record voice with Gemini Live"
              className="flex items-center gap-1.5 px-3 py-2.5 rounded-lg bg-[#0d1117] text-emerald-400 hover:text-white hover:bg-emerald-600/30 border border-emerald-500/50 hover:border-emerald-400 font-mono text-xs font-medium transition-all shrink-0 disabled:opacity-40"
            >
              <Mic className="w-4 h-4 text-emerald-400" />
              <span>Voice</span>
            </button>
          )}

          <input
            type="text"
            value={inputPrompt}
            onChange={(e) => setInputPrompt(e.target.value)}
            placeholder={
              isListening
                ? `Recording voice in ${language.toUpperCase()}... Click Stop & Send when done`
                : language === 'hinglish'
                ? 'Type in Hinglish or English... (or click Voice to speak)'
                : language === 'hindi'
                ? 'हिंदी में टाइप करें... (या बोलने के लिए Voice दबाएं)'
                : 'Type well query for text response... (or click Voice to speak)'
            }
            disabled={isProcessing || isListening}
            className="flex-1 bg-[#0d1117] border border-border text-xs px-3 py-2.5 rounded-lg text-white placeholder-textMuted focus:outline-none focus:border-accent font-sans"
          />

          <button
            type="submit"
            disabled={!inputPrompt.trim() || isProcessing}
            className="p-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:hover:bg-blue-600 text-white transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
};
