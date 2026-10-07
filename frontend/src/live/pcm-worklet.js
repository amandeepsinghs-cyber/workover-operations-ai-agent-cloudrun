/**
 * pcm-worklet.js - AudioWorkletProcessor for microphone downsampling.
 *
 * Runs in AudioWorkletGlobalScope. Resamples browser audio input to 16,000 Hz mono PCM16
 * little-endian and posts chunks of ~30 ms (480 samples = 960 bytes) to the main thread.
 *
 * Wire protocol requirement:
 * Client -> server: binary ArrayBuffer of 16 kHz PCM16 mono little-endian (~20-40ms chunks).
 */

class PcmWorkletProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    /** @type {number} Target sample rate expected by Gemini Live API */
    this.targetSampleRate = 16000;

    /** @type {number} 480 samples @ 16 kHz = 30 ms chunk (960 bytes Int16) */
    this.chunkSize = 480;

    /** @type {Int16Array} */
    this.outputBuffer = new Int16Array(this.chunkSize);
    this.outputIndex = 0;

    /** @type {number[]} Buffer for input Float32 samples */
    this.inputBuffer = [];

    /** @type {number} Resampling ratio (inputRate / targetRate) */
    this.ratio = sampleRate / this.targetSampleRate;

    /** @type {number} Fractional phase position in inputBuffer */
    this.phase = 0;

    /** @type {boolean} Gated capture state */
    this.enabled = false;

    this.port.onmessage = (event) => {
      const data = event.data;
      if (!data) return;
      if (typeof data.enabled === 'boolean') {
        this.enabled = data.enabled;
        if (!this.enabled) {
          // Flush internal buffers on disable to prevent stale voice data on next turn
          this.inputBuffer = [];
          this.phase = 0;
          this.outputIndex = 0;
        }
      }
    };
  }

  /**
   * Main audio rendering callback.
   * @param {Float32Array[][]} inputs
   * @param {Float32Array[][]} outputs
   * @param {Record<string, Float32Array>} parameters
   * @returns {boolean}
   */
  process(inputs, outputs, parameters) {
    if (!this.enabled) return true;

    const input = inputs[0];
    if (!input || !input[0] || input[0].length === 0) return true;

    const channelData = input[0];

    // Case 1: Browser audio context is already 16 kHz (no resampling needed)
    if (sampleRate === this.targetSampleRate) {
      for (let i = 0; i < channelData.length; i++) {
        const s = Math.max(-1, Math.min(1, channelData[i]));
        this.outputBuffer[this.outputIndex++] = s < 0 ? s * 0x8000 : s * 0x7fff;
        if (this.outputIndex === this.chunkSize) {
          this.port.postMessage(this.outputBuffer.buffer, [this.outputBuffer.buffer]);
          this.outputBuffer = new Int16Array(this.chunkSize);
          this.outputIndex = 0;
        }
      }
      return true;
    }

    // Case 2: Downsample from context rate (e.g. 48000 or 44100 Hz) to 16000 Hz using linear interpolation
    for (let i = 0; i < channelData.length; i++) {
      this.inputBuffer.push(channelData[i]);
    }

    while (this.phase < this.inputBuffer.length - 1) {
      const idx = Math.floor(this.phase);
      const frac = this.phase - idx;
      const s0 = this.inputBuffer[idx];
      const s1 = this.inputBuffer[idx + 1];
      const s = Math.max(-1, Math.min(1, s0 + frac * (s1 - s0)));

      this.outputBuffer[this.outputIndex++] = s < 0 ? s * 0x8000 : s * 0x7fff;
      if (this.outputIndex === this.chunkSize) {
        this.port.postMessage(this.outputBuffer.buffer, [this.outputBuffer.buffer]);
        this.outputBuffer = new Int16Array(this.chunkSize);
        this.outputIndex = 0;
      }

      this.phase += this.ratio;
    }

    // Retain only samples still needed for future interpolation
    const removeCount = Math.min(Math.floor(this.phase), Math.max(0, this.inputBuffer.length - 1));
    if (removeCount > 0) {
      this.inputBuffer.splice(0, removeCount);
      this.phase -= removeCount;
    }

    return true;
  }
}

registerProcessor('pcm-worklet', PcmWorkletProcessor);
registerProcessor('pcm-worklet-processor', PcmWorkletProcessor);
