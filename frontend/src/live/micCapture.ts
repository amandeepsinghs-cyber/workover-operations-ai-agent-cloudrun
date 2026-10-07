/**
 * micCapture.ts — 16 kHz 16-bit linear PCM microphone capture via AudioWorklet.
 *
 * Uses getUserMedia with echoCancellation, noiseSuppression, and autoGainControl,
 * then feeds audio into pcm-worklet.js to downsample to 16,000 Hz mono PCM16 little-endian.
 * Emits ArrayBuffer chunks from the worklet to the onChunk callback.
 */

import workletUrl from './pcm-worklet.js?url';

export type PcmChunkCallback = (buf: ArrayBuffer) => void;

export class MicCapture {
  private audioCtx: AudioContext | null = null;
  private mediaStream: MediaStream | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private workletNode: AudioWorkletNode | null = null;
  private muteGain: GainNode | null = null;
  private active = false;
  private enabled = false;
  private onChunkCallback: PcmChunkCallback | null = null;

  public async start(onChunk: PcmChunkCallback): Promise<void> {
    this.onChunkCallback = onChunk;
    if (this.active) {
      this.enable(true);
      return;
    }

    try {
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      this.audioCtx = new AudioCtx();
      if (this.audioCtx.state === 'suspended') {
        await this.audioCtx.resume();
      }

      await this.audioCtx.audioWorklet.addModule(workletUrl);

      this.source = this.audioCtx.createMediaStreamSource(this.mediaStream);
      this.workletNode = new AudioWorkletNode(this.audioCtx, 'pcm-worklet');

      this.workletNode.port.onmessage = (event: MessageEvent) => {
        if (!this.enabled || !this.onChunkCallback) return;
        if (event.data instanceof ArrayBuffer) {
          this.onChunkCallback(event.data);
        }
      };

      // Connect worklet output through a GainNode(gain 0) to destination so process() runs
      this.muteGain = this.audioCtx.createGain();
      this.muteGain.gain.value = 0;
      this.source.connect(this.workletNode);
      this.workletNode.connect(this.muteGain);
      this.muteGain.connect(this.audioCtx.destination);

      this.active = true;
      this.enable(true);
    } catch (err) {
      this.stop();
      throw err;
    }
  }

  public enable(on: boolean): void {
    this.enabled = !!on;
    if (this.workletNode) {
      this.workletNode.port.postMessage({ enabled: this.enabled });
    }
    if (this.audioCtx && this.enabled && this.audioCtx.state === 'suspended') {
      this.audioCtx.resume().catch(() => {});
    }
  }

  public stop(): void {
    this.active = false;
    this.enabled = false;
    this.onChunkCallback = null;

    if (this.workletNode) {
      try {
        this.workletNode.port.postMessage({ enabled: false });
        this.workletNode.disconnect();
      } catch (_) {}
      this.workletNode = null;
    }

    if (this.muteGain) {
      try {
        this.muteGain.disconnect();
      } catch (_) {}
      this.muteGain = null;
    }

    if (this.source) {
      try {
        this.source.disconnect();
      } catch (_) {}
      this.source = null;
    }

    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
      this.mediaStream = null;
    }

    if (this.audioCtx && this.audioCtx.state !== 'closed') {
      this.audioCtx.close().catch(() => {});
      this.audioCtx = null;
    }
  }

  public isCapturing(): boolean {
    return this.active;
  }
}

export const micCapture = new MicCapture();
