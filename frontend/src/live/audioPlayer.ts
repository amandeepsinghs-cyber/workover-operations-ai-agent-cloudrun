/**
 * audioPlayer — 24 kHz 16-bit linear PCM audio player with jitter buffer and barge-in.
 * Receives raw PCM chunks from Gemini Live over WebSocket and schedules playback smoothly.
 */

export class AudioPlayer {
  private audioCtx: AudioContext | null = null;
  private nextPlayTime = 0;
  private activeSources: AudioBufferSourceNode[] = [];
  private sampleRate = 24000;
  private isPlaying = false;

  public async resume(): Promise<void> {
    const ctx = this.initContext();
    if (ctx.state === 'suspended') {
      await ctx.resume().catch(() => {});
    }
  }

  public initContext(): AudioContext {
    if (!this.audioCtx || this.audioCtx.state === 'closed') {
      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      this.audioCtx = new AudioCtx({ sampleRate: this.sampleRate });
    }
    if (this.audioCtx.state === 'suspended') {
      this.audioCtx.resume().catch(() => {});
    }
    return this.audioCtx;
  }

  public playPcmChunk(pcmData: ArrayBuffer | Uint8Array): void {
    const ctx = this.initContext();
    const pcm16 = new Int16Array(
      pcmData instanceof Uint8Array
        ? pcmData.buffer.slice(pcmData.byteOffset, pcmData.byteOffset + pcmData.byteLength)
        : pcmData
    );

    if (pcm16.length === 0) return;

    // Convert Int16 PCM to Float32 [-1.0, 1.0]
    const float32 = new Float32Array(pcm16.length);
    for (let i = 0; i < pcm16.length; i++) {
      float32[i] = pcm16[i] / 32768.0;
    }

    const audioBuffer = ctx.createBuffer(1, float32.length, this.sampleRate);
    audioBuffer.copyToChannel(float32, 0);

    const source = ctx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(ctx.destination);

    const currentTime = ctx.currentTime;
    if (this.nextPlayTime < currentTime) {
      // 50 ms buffer offset to prevent underrun
      this.nextPlayTime = currentTime + 0.05;
    }

    source.start(this.nextPlayTime);
    this.nextPlayTime += audioBuffer.duration;
    this.activeSources.push(source);
    this.isPlaying = true;

    source.onended = () => {
      const idx = this.activeSources.indexOf(source);
      if (idx !== -1) {
        this.activeSources.splice(idx, 1);
      }
      if (this.activeSources.length === 0) {
        this.isPlaying = false;
      }
    };
  }

  /**
   * Barge-in interruption: immediately halts all playing and scheduled audio buffers.
   */
  public interrupt(): void {
    for (const source of this.activeSources) {
      try {
        source.stop();
        source.disconnect();
      } catch (_) {
        // Source might already have ended
      }
    }
    this.activeSources = [];
    this.isPlaying = false;
    if (this.audioCtx) {
      this.nextPlayTime = this.audioCtx.currentTime;
    }
  }

  public getIsPlaying(): boolean {
    return this.isPlaying;
  }
}

export const audioPlayer = new AudioPlayer();
