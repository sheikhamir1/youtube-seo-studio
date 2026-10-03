import { describe, expect, it } from 'vitest';

import {
  filenameToTitle,
  formatBytes,
  formatDuration,
  formatTimestamp,
  truncate,
} from '../src/utils/format';
import { cn } from '../src/utils/cn';

describe('formatTimestamp', () => {
  it('formats sub-hour values as mm:ss', () => {
    expect(formatTimestamp(0)).toBe('00:00');
    expect(formatTimestamp(65)).toBe('01:05');
    expect(formatTimestamp(3599)).toBe('59:59');
  });

  it('formats hour values as h:mm:ss', () => {
    expect(formatTimestamp(3600)).toBe('1:00:00');
    expect(formatTimestamp(3662)).toBe('1:01:02');
    expect(formatTimestamp(43200)).toBe('12:00:00');
  });

  it('handles invalid input without throwing', () => {
    expect(formatTimestamp(null)).toBe('00:00');
    expect(formatTimestamp(undefined)).toBe('00:00');
    expect(formatTimestamp(Number.NaN)).toBe('00:00');
    expect(formatTimestamp(-10)).toBe('00:00');
  });
});

describe('formatDuration', () => {
  it('renders human readable durations', () => {
    expect(formatDuration(45)).toBe('45s');
    expect(formatDuration(90)).toBe('1m 30s');
    expect(formatDuration(7200)).toBe('2h 00m 00s');
  });

  it('marks unknown durations explicitly', () => {
    expect(formatDuration(null)).toBe('unknown');
  });
});

describe('formatBytes', () => {
  it('uses binary units', () => {
    expect(formatBytes(0)).toBe('0 B');
    expect(formatBytes(1024)).toBe('1.0 KB');
    expect(formatBytes(1024 ** 2)).toBe('1.0 MB');
    expect(formatBytes(32 * 1024 ** 2)).toBe('32.0 MB');
  });
});

describe('filenameToTitle', () => {
  it('turns file names into readable titles', () => {
    expect(filenameToTitle('advanced-rag-session_4.mp4')).toBe('advanced rag session 4');
    expect(filenameToTitle('')).toBe('');
  });
});

describe('truncate and cn', () => {
  it('truncates with an ellipsis', () => {
    expect(truncate('abcdef', 4)).toBe('abc…');
    expect(truncate('abc', 10)).toBe('abc');
  });

  it('joins truthy class names only', () => {
    expect(cn('a', undefined, 'c', null)).toBe('a c');
  });
});
