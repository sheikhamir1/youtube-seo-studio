import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../src/services/api/uploads', () => ({
  createUploadSession: vi.fn(),
  getUploadSession: vi.fn(),
  uploadPart: vi.fn(),
  completeUpload: vi.fn(),
  abortUpload: vi.fn(),
}));

import {
  abortUpload,
  completeUpload,
  createUploadSession,
  getUploadSession,
  uploadPart,
} from '../src/services/api/uploads';
import { UploadController, loadActiveUpload, saveActiveUpload } from '../src/services/upload/uploadService';

const makeFile = (bytes) => {
  return {
    name: 'lecture.mp4',
    size: bytes,
    type: 'video/mp4',
    slice: (start, end) => ({ start, end, size: end - start }),
  };
};

const session = (overrides = {}) => ({
  id: 'upload-1',
  chunk_size: 32,
  total_parts: 4,
  received_size: 0,
  expected_size: 128,
  next_missing_part: 0,
  status: 'IN_PROGRESS',
  original_filename: 'lecture.mp4',
  ...overrides,
});

describe('UploadController', () => {
  beforeEach(() => {
    createUploadSession.mockReset();
    getUploadSession.mockReset();
    uploadPart.mockReset();
    completeUpload.mockReset();
    abortUpload.mockReset();
  });

  it('uploads one part at a time and completes the session', async () => {
    createUploadSession.mockResolvedValue({ data: session() });
    uploadPart.mockResolvedValue({ received_size: 32 });
    completeUpload.mockResolvedValue({ data: { id: 'upload-1', status: 'COMPLETED' } });

    const seenParts = [];
    uploadPart.mockImplementation(async ({ partNumber }) => {
      seenParts.push(partNumber);
      return { received_size: (partNumber + 1) * 32 };
    });

    const controller = new UploadController({ file: makeFile(128) });
    const outcome = await controller.start();

    expect(outcome.status).toBe('completed');
    expect(seenParts).toEqual([0, 1, 2, 3]);
    expect(completeUpload).toHaveBeenCalledWith('upload-1', 128);
    expect(controller.progressPercent).toBe(100);
  });

  it('resumes from the part the server is still missing', async () => {
    getUploadSession.mockResolvedValue(
      session({ received_size: 64, next_missing_part: 2, status: 'IN_PROGRESS' }),
    );
    const seenParts = [];
    uploadPart.mockImplementation(async ({ partNumber }) => {
      seenParts.push(partNumber);
      return { received_size: (partNumber + 1) * 32 };
    });
    completeUpload.mockResolvedValue({ data: { id: 'upload-1', status: 'COMPLETED' } });

    const controller = new UploadController({ file: makeFile(128) });
    await controller.resume('upload-1');

    expect(seenParts).toEqual([2, 3]);
  });

  it('does not upload further parts after a pause', async () => {
    createUploadSession.mockResolvedValue({ data: session() });
    let controller;
    uploadPart.mockImplementation(async ({ partNumber }) => {
      if (partNumber === 0) controller.pause();
      return { received_size: (partNumber + 1) * 32 };
    });

    controller = new UploadController({ file: makeFile(128) });
    const outcome = await controller.start();

    expect(outcome.status).toBe('paused');
    expect(uploadPart).toHaveBeenCalledTimes(1);
    expect(completeUpload).not.toHaveBeenCalled();
  });

  it('aborts the server session on cancel and clears the stored resume state', async () => {
    createUploadSession.mockResolvedValue({ data: session() });
    uploadPart.mockResolvedValue({ received_size: 32 });
    abortUpload.mockResolvedValue({ id: 'upload-1' });

    const controller = new UploadController({ file: makeFile(128) });
    const promise = controller.start();
    await controller.cancel();
    await promise;

    expect(abortUpload).toHaveBeenCalledWith('upload-1');
    expect(loadActiveUpload()).toBeNull();
  });
});

describe('resume state', () => {
  it('persists and restores the active upload session', () => {
    saveActiveUpload({ uploadId: 'upload-9', filename: 'a.mp4', receivedSize: 10 });
    expect(loadActiveUpload()).toMatchObject({ uploadId: 'upload-9', receivedSize: 10 });
  });
});
