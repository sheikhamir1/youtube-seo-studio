/**
 * Resumable upload client.
 *
 * Sends one 32 MiB part at a time (never the whole video, never several huge
 * requests in parallel), reports real progress, supports pause/resume/cancel and
 * remembers the session id so a page refresh continues instead of restarting.
 */

import { UPLOAD_PART_SIZE_BYTES, UPLOAD_SESSION_STORAGE_KEY } from '../../constants';
import {
  abortUpload,
  completeUpload,
  createUploadSession,
  getUploadSession,
  uploadPart,
} from '../api/uploads';

export function saveActiveUpload(state) {
  try {
    if (!state) {
      localStorage.removeItem(UPLOAD_SESSION_STORAGE_KEY);
      return;
    }
    localStorage.setItem(UPLOAD_SESSION_STORAGE_KEY, JSON.stringify(state));
  } catch {
    /* storage may be unavailable: the upload still works, only resume is lost */
  }
}

export function loadActiveUpload() {
  try {
    const raw = localStorage.getItem(UPLOAD_SESSION_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function clearActiveUpload() {
  try {
    localStorage.removeItem(UPLOAD_SESSION_STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

export class UploadController {
  /**
   * @param {object} options
   * @param {File} options.file
   * @param {(progress: object) => void} [options.onProgress]
   * @param {(session: object) => void} [options.onSession]
   */
  constructor({ file, onProgress, onSession }) {
    this.file = file;
    this.onProgress = onProgress || (() => {});
    this.onSession = onSession || (() => {});
    this.sessionId = null;
    this.partSize = UPLOAD_PART_SIZE_BYTES;
    this.uploadedBytes = 0;
    this.nextPart = 0;
    this.totalParts = 0;
    this.status = 'idle'; // idle | uploading | paused | completed | canceled | failed
    this.bytesPerSecond = 0;
    this._controller = null;
    this._cancelRequested = false;
    this._startedAt = 0;
    this._lastSampleAt = 0;
    this._lastSampleBytes = 0;
  }

  get progressPercent() {
    if (!this.file?.size) return 0;
    return Math.min(100, (this.uploadedBytes / this.file.size) * 100);
  }

  get missingParts() {
    const missing = [];
    for (let part = this.nextPart; part < this.totalParts; part += 1) missing.push(part);
    return missing;
  }

  _emit(extra = {}) {
    const elapsed = this._startedAt ? (Date.now() - this._startedAt) / 1000 : 0;
    this.onProgress({
      filename: this.file?.name || '',
      sizeBytes: this.file?.size || 0,
      uploadedBytes: this.uploadedBytes,
      remainingBytes: Math.max(0, (this.file?.size || 0) - this.uploadedBytes),
      percent: this.progressPercent,
      bytesPerSecond: this.bytesPerSecond,
      etaSeconds:
        this.bytesPerSecond > 0 && this.file?.size
          ? Math.max(0, (this.file.size - this.uploadedBytes) / this.bytesPerSecond)
          : null,
      elapsedSeconds: elapsed,
      totalParts: this.totalParts,
      nextPart: this.nextPart,
      status: this.status,
      ...extra,
    });
  }

  async start() {
    this.status = 'uploading';
    this._startedAt = Date.now();
    this._lastSampleAt = Date.now();
    try {
      const session = await createUploadSession({
        filename: this.file.name,
        contentType: this.file.type || 'application/octet-stream',
        sizeBytes: this.file.size,
        chunkSizeBytes: this.partSize,
      });
      this._adoptSession(session.data ?? session);
      if (this._cancelRequested) {
        // The user cancelled while the session was being created.
        await this.cancel();
        return { status: 'canceled', sessionId: this.sessionId };
      }
      return await this._run();
    } catch (error) {
      this.status = 'failed';
      this._emit({ error });
      throw error;
    }
  }

  /** Attach to an existing session (used after a page refresh). */
  async resume(uploadId) {
    this.status = 'uploading';
    this._startedAt = Date.now();
    this._lastSampleAt = Date.now();
    const session = await getUploadSession(uploadId);
    this._adoptSession(session);
    if (this._cancelRequested) {
      await this.cancel();
      return { status: 'canceled', sessionId: this.sessionId };
    }
    return this._run();
  }

  _adoptSession(session) {
    this.sessionId = session.id;
    this.partSize = session.chunk_size || this.partSize;
    this.totalParts = session.total_parts;
    this.uploadedBytes = session.received_size || 0;
    this.nextPart = session.next_missing_part ?? Math.floor(this.uploadedBytes / this.partSize);
    saveActiveUpload({
      uploadId: session.id,
      filename: session.original_filename || this.file?.name,
      sizeBytes: session.expected_size,
      receivedSize: session.received_size,
      partSize: this.partSize,
      totalParts: this.totalParts,
    });
    this.onSession(session);
    this._emit();
  }

  async _run() {
    while (this.nextPart < this.totalParts) {
      if (this.status === 'paused' || this.status === 'canceled') {
        this._emit();
        return { status: this.status, sessionId: this.sessionId };
      }
      await this._uploadOnePart(this.nextPart);
    }
    const completed = await completeUpload(this.sessionId, this.file.size);
    this.status = 'completed';
    this.uploadedBytes = this.file.size;
    this.onSession(completed.data);
    this._emit({ session: completed.data });
    clearActiveUpload();
    return { status: 'completed', sessionId: this.sessionId, session: completed.data };
  }

  async _uploadOnePart(partNumber) {
    const start = partNumber * this.partSize;
    const end = Math.min(start + this.partSize, this.file.size);
    // Blob.slice keeps the video out of browser memory.
    const blob = this.file.slice(start, end);
    this._controller = new AbortController();

    const partResult = await uploadPart({
      uploadId: this.sessionId,
      partNumber,
      blob,
      signal: this._controller.signal,
      onUploadProgress: (event) => {
        if (!event?.loaded) return;
        this.uploadedBytes = Math.min(this.file.size, start + event.loaded);
        const now = Date.now();
        const deltaSeconds = (now - this._lastSampleAt) / 1000;
        if (deltaSeconds >= 0.5) {
          this.bytesPerSecond = (this.uploadedBytes - this._lastSampleBytes) / deltaSeconds;
          this._lastSampleAt = now;
          this._lastSampleBytes = this.uploadedBytes;
        }
        this._emit();
      },
    });

    this.uploadedBytes = Math.min(this.file.size, end);
    this.nextPart = partNumber + 1;
    saveActiveUpload({
      uploadId: this.sessionId,
      filename: this.file?.name,
      sizeBytes: this.file?.size,
      receivedSize: partResult?.received_size ?? this.uploadedBytes,
      partSize: this.partSize,
      totalParts: this.totalParts,
    });
    this._emit();
  }

  pause() {
    if (this.status !== 'uploading') return;
    this.status = 'paused';
    this._controller?.abort();
    this._emit();
  }

  async resumeUpload() {
    if (this.status !== 'paused') return undefined;
    this.status = 'uploading';
    return this._run();
  }

  async cancel() {
    this.status = 'canceled';
    this._cancelRequested = true;
    this._controller?.abort();
    if (this.sessionId) {
      try {
        await abortUpload(this.sessionId);
      } catch {
        /* the session may already be gone */
      }
    }
    clearActiveUpload();
    this._emit();
  }
}

export const PART_SIZE_BYTES = UPLOAD_PART_SIZE_BYTES;
