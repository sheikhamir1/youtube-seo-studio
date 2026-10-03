import { describe, expect, it } from 'vitest';

import { extractChapters, parseTimestamp, validateChapters } from '../src/utils/chapters';

const VALID_DESCRIPTION = `Welcome to the session.

00:00 Introduction
05:30 Why retrieval matters
1:02:10 Building the index
1:45:00 Wrap-up and next steps`;

describe('parseTimestamp', () => {
  it('parses both mm:ss and h:mm:ss', () => {
    expect(parseTimestamp('00:00')).toBe(0);
    expect(parseTimestamp('05:30')).toBe(330);
    expect(parseTimestamp('1:02:10')).toBe(3730);
  });

  it('rejects impossible minute/second values', () => {
    expect(parseTimestamp('90:00')).toBeNull();
    expect(parseTimestamp('10:75')).toBeNull();
  });
});

describe('extractChapters', () => {
  it('finds every timestamped line', () => {
    const chapters = extractChapters(VALID_DESCRIPTION);
    expect(chapters).toHaveLength(4);
    expect(chapters.map((chapter) => chapter.seconds)).toEqual([0, 330, 3730, 6300]);
    expect(chapters[1].title).toBe('Why retrieval matters');
  });

  it('ignores prose lines', () => {
    expect(extractChapters('There is no timestamp on this line.')).toHaveLength(0);
  });
});

describe('validateChapters', () => {
  it('passes a well-formed chapter block', () => {
    const report = validateChapters(VALID_DESCRIPTION, { videoDurationSeconds: 6600 });
    expect(report.valid).toBe(true);
    expect(report.checks.startsAtZero).toBe(true);
    expect(report.checks.chronological).toBe(true);
    expect(report.checks.withinDuration).toBe(true);
    expect(report.issues).toEqual([]);
  });

  it('fails when the description starts late', () => {
    const report = validateChapters('05:00 Intro\n10:00 Body\n15:00 End');
    expect(report.valid).toBe(false);
    expect(report.checks.startsAtZero).toBe(false);
  });

  it('fails when fewer than three chapters are present', () => {
    const report = validateChapters('00:00 Intro\n10:00 End');
    expect(report.checks.minimumCount).toBe(false);
    expect(report.valid).toBe(false);
  });

  it('fails when chapters are closer than ten seconds', () => {
    const report = validateChapters('00:00 Intro\n00:05 Too soon\n00:20 Later');
    expect(report.checks.spacingValid).toBe(false);
  });

  it('fails when a timestamp exceeds the video duration', () => {
    const report = validateChapters('00:00 Intro\n10:00 Body\n01:30:00 Beyond', {
      videoDurationSeconds: 600,
    });
    expect(report.checks.withinDuration).toBe(false);
  });
});
