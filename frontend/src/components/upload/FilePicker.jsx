import { FileVideo, UploadCloud, X } from 'lucide-react';
import { useRef, useState } from 'react';

import { formatBytes } from '../../utils/format';
import { cn } from '../../utils/cn';
import Button from '../ui/Button';

/** Accepted containers: the pipeline only needs a video with an audio stream. */
const ACCEPTED_EXTENSIONS = ['.mp4', '.mkv', '.mov', '.avi', '.webm', '.m4v', '.flv', '.ts', '.mpg', '.mpeg', '.wmv'];

/**
 * Drag-and-drop / click file picker. Validates basic expectations locally and
 * explains exactly what is wrong instead of failing later in FFprobe.
 */
export function FilePicker({ file, onSelect, onClear, disabled = false }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState(null);

  const validate = (candidate) => {
    if (!candidate) return 'No file selected.';
    const name = candidate.name.toLowerCase();
    if (!ACCEPTED_EXTENSIONS.some((extension) => name.endsWith(extension))) {
      return `Unsupported file type. Supported: ${ACCEPTED_EXTENSIONS.join(', ')}.`;
    }
    if (candidate.size === 0) return 'That file is empty.';
    return null;
  };

  const handleFile = (candidate) => {
    const problem = validate(candidate);
    setError(problem);
    if (!problem) onSelect(candidate);
  };

  return (
    <div>
      <div
        onDragOver={(event) => {
          event.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          if (disabled) return;
          handleFile(event.dataTransfer.files?.[0]);
        }}
        className={cn(
          'flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed p-6 text-center transition-colors',
          dragging ? 'border-accent bg-accent/5' : 'border-border',
          disabled && 'opacity-60',
        )}
      >
        <UploadCloud className="h-7 w-7 text-muted" aria-hidden="true" />
        <div>
          <p className="text-sm font-medium">Drag your video here</p>
          <p className="mt-0.5 text-xs text-muted">
            Large files are uploaded in 32 MiB parts and can be resumed after a refresh.
          </p>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_EXTENSIONS.join(',')}
          className="sr-only"
          disabled={disabled}
          onChange={(event) => {
            handleFile(event.target.files?.[0]);
            event.target.value = '';
          }}
        />
        <Button
          variant="outline"
          size="sm"
          icon={FileVideo}
          disabled={disabled}
          onClick={() => inputRef.current?.click()}
        >
          Choose video file
        </Button>
        <p className="text-[11px] text-muted">
          The original video never leaves this machine - only extracted audio chunks are sent to Gemini.
        </p>
      </div>

      {error && (
        <p role="alert" className="mt-2 text-xs text-danger">
          {error}
        </p>
      )}

      {file && (
        <div className="mt-3 flex items-center justify-between gap-3 rounded-md border border-border bg-surface-2 px-3 py-2">
          <div className="flex min-w-0 items-center gap-2">
            <FileVideo className="h-4 w-4 shrink-0 text-accent" aria-hidden="true" />
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{file.name}</p>
              <p className="text-xs text-muted">{formatBytes(file.size)}</p>
            </div>
          </div>
          {onClear && (
            <Button
              variant="ghost"
              size="xs"
              icon={X}
              aria-label="Remove selected file"
              disabled={disabled}
              onClick={onClear}
            />
          )}
        </div>
      )}
    </div>
  );
}

export default FilePicker;
