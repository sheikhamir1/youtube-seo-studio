/** Client-side chapter helpers (mirrors the backend validator for live UI feedback). */

import { formatTimestamp } from './format';

const CHAPTER_LINE = /^\s*(\d{1,2}:\d{2}:\d{2}|\d{1,3}:\d{2})\s*(?:[-–—:.)]\s*)?(\S.*)?$/;
const MIN_SPACING_SECONDS = 10;

export function parseTimestamp(value) {
  const match = /^(\d{1,3}):(\d{2})(?::(\d{2}))?$/.exec(String(value || '').trim());
  if (!match) return null;
  const [first, second, third] = [match[1], match[2], match[3]];
  if (third !== undefined) {
    const minutes = Number(second);
    const seconds = Number(third);
    if (minutes >= 60 || seconds >= 60) return null;
    return Number(first) * 3600 + minutes * 60 + seconds;
  }
  const minutes = Number(first);
  const seconds = Number(second);
  // Mirrors the backend rule: "MM:SS" with minutes >= 60 is an impossible
  // timestamp (long values must be written as H:MM:SS).
  if (minutes >= 60 || seconds >= 60) return null;
  return minutes * 60 + seconds;
}

export function extractChapters(description) {
  const lines = String(description || '').split('\n');
  const chapters = [];
  lines.forEach((line) => {
    const match = CHAPTER_LINE.exec(line);
    if (!match) return;
    const seconds = parseTimestamp(match[1]);
    if (seconds === null) return;
    chapters.push({
      seconds,
      timestamp: formatTimestamp(seconds),
      title: (match[2] || '').trim(),
      line,
    });
  });
  return chapters;
}

export function validateChapters(description, { videoDurationSeconds } = {}) {
  const chapters = extractChapters(description);
  const seconds = chapters.map((chapter) => chapter.seconds);
  const checks = {
    startsAtZero: chapters.length > 0 && seconds[0] === 0,
    chronological: seconds.every((value, index) => index === 0 || seconds[index - 1] < value),
    minimumCount: chapters.length >= 3,
    spacingValid: seconds.every(
      (value, index) => index === 0 || value - seconds[index - 1] >= MIN_SPACING_SECONDS,
    ),
    withinDuration:
      !videoDurationSeconds || seconds.every((value) => value <= videoDurationSeconds + 1.5),
    titlesPresent: chapters.every((chapter) => chapter.title.length > 0),
  };
  const issues = [];
  if (!checks.startsAtZero) issues.push('The first chapter timestamp must be 00:00.');
  if (!checks.chronological) issues.push('Chapter timestamps must be ascending.');
  if (!checks.minimumCount) issues.push('Add at least three chapters for long-form content.');
  if (!checks.spacingValid) issues.push('Chapters must be at least 10 seconds apart.');
  if (!checks.withinDuration) issues.push('A chapter timestamp is beyond the video duration.');
  if (!checks.titlesPresent) issues.push('Every chapter needs a title.');
  return { chapters, checks, issues, valid: issues.length === 0 };
}

const CHECK_LABELS = {
  startsAtZero: 'Starts at 00:00',
  chronological: 'Chronological',
  minimumCount: '3+ chapters',
  spacingValid: 'Chapter spacing valid',
  withinDuration: 'All timestamps within video duration',
  titlesPresent: 'Every chapter has a title',
};

export const chapterCheckLabel = (key) => CHECK_LABELS[key] || key;
