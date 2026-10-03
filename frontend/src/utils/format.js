/** Shared formatting helpers (mirrors the backend's timestamp rules). */

export function formatTimestamp(seconds) {
  if (seconds === null || seconds === undefined || Number.isNaN(Number(seconds))) return '00:00';
  const safe = Math.max(0, Math.round(Number(seconds)));
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const secs = safe % 60;
  const pad = (value) => String(value).padStart(2, '0');
  return hours > 0 ? `${hours}:${pad(minutes)}:${pad(secs)}` : `${pad(minutes)}:${pad(secs)}`;
}

export function formatDuration(seconds) {
  if (seconds === null || seconds === undefined || Number.isNaN(Number(seconds))) return 'unknown';
  const total = Math.max(0, Math.round(Number(seconds)));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  const pad = (value) => String(value).padStart(2, '0');
  if (hours) return `${hours}h ${pad(minutes)}m ${pad(secs)}s`;
  if (minutes) return `${minutes}m ${pad(secs)}s`;
  return `${secs}s`;
}

export function formatShortDuration(seconds) {
  if (!seconds && seconds !== 0) return '—';
  const total = Math.round(Number(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  if (hours) return `${hours}h ${String(minutes).padStart(2, '0')}m`;
  return `${minutes}m`;
}

export function formatBytes(bytes, fractionDigits = 1) {
  if (bytes === null || bytes === undefined || Number.isNaN(Number(bytes))) return '—';
  const value = Number(bytes);
  if (value <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const exponent = Math.min(units.length - 1, Math.floor(Math.log(value) / Math.log(1024)));
  const scaled = value / 1024 ** exponent;
  return `${scaled.toFixed(exponent === 0 ? 0 : fractionDigits)} ${units[exponent]}`;
}

export function formatDateTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function formatRelative(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  const diffSeconds = Math.round((Date.now() - date.getTime()) / 1000);
  const table = [
    [60, 'second'],
    [60, 'minute'],
    [24, 'hour'],
    [30, 'day'],
    [12, 'month'],
  ];
  let unit = 'second';
  let amount = diffSeconds;
  for (const [size, name] of table) {
    if (Math.abs(amount) < size) {
      unit = name;
      break;
    }
    amount = Math.round(amount / size);
    unit = name;
  }
  try {
    return new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' }).format(-amount, unit);
  } catch {
    return formatDateTime(value);
  }
}

export function formatNumber(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return new Intl.NumberFormat().format(Number(value));
}

export function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '0%';
  return `${Math.round(Number(value))}%`;
}

export function truncate(text, maxLength = 80) {
  const value = String(text || '');
  if (value.length <= maxLength) return value;
  return `${value.slice(0, maxLength - 1)}…`;
}

/** File name -> readable title (used as the default video title). */
export function filenameToTitle(filename) {
  if (!filename) return '';
  const stem = filename.replace(/\.[^.]+$/, '');
  return stem.replace(/[_-]+/g, ' ').replace(/\s+/g, ' ').trim();
}
