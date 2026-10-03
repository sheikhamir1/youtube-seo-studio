import { Copy } from 'lucide-react';

import { formatTimestamp } from '../../utils/format';
import Button from '../ui/Button';
import CopyButton from '../ui/CopyButton';
import { Card, CardBody, CardFooter, CardHeader } from '../ui/Card';
import ScoreGauge from './ScoreGauge';

const asList = (value) => String(value || '').split('\n').map((line) => line.replace(/^[-*\d.\s]+/, '').trim()).filter(Boolean);

/**
 * Read-only presentation of one full SEO result plus the "copy everything"
 * action that makes the tool usable day to day.
 */
export function SeoOutputView({ result, job, chapters = [], onEdit }) {
  if (!result) return null;

  const readOnlyText = [
    `TITLE:\n${result.title}`,
    `\nDESCRIPTION:\n${result.description}`,
    `\nTAGS:\n${(result.tags || []).join(', ')}`,
    `\nSEO SCORE: ${result.seo_score}/100`,
    `\nIMPROVEMENT SUGGESTIONS:\n${result.improvement_suggestions}`,
    `\nTHUMBNAIL PROMPT:\n${result.thumbnail_prompt}`,
  ].join('\n');

  return (
    <Card>
      <CardHeader
        title="SEO output"
        description={`Version ${result.version_number}${result.edited_by_user ? ' (edited)' : ''} · generated with ${result.model}`}
        actions={
          <>
            {onEdit && (
              <Button variant="outline" size="sm" onClick={onEdit}>
                Edit
              </Button>
            )}
            <CopyButton value={readOnlyText} label="Copy everything" variant="primary" />
          </>
        }
      />
      <CardBody className="space-y-5">
        <ScoreGauge score={result.seo_score} />

        <div>
          <h3 className="mb-1">Title</h3>
          <div className="flex items-start justify-between gap-3">
            <p className="text-base font-medium">{result.title}</p>
            <CopyButton value={result.title} label="Copy" size="xs" variant="ghost" />
          </div>
          <p className="mono mt-0.5 text-xs text-muted">{result.title.length} characters</p>
        </div>

        <div>
          <h3 className="mb-1">Description</h3>
          <div className="flex items-start justify-between gap-3">
            <p className="whitespace-pre-wrap text-sm">{result.description}</p>
            <CopyButton value={result.description} label="Copy" size="xs" variant="ghost" />
          </div>
          <p className="mono mt-0.5 text-xs text-muted">{result.description.length} characters</p>
        </div>

        <div>
          <h3 className="mb-1">Tags ({result.tags?.length || 0})</h3>
          <div className="flex flex-wrap gap-1.5">
            {(result.tags || []).map((tag) => (
              <span key={tag} className="rounded border border-border bg-surface-2 px-2 py-0.5 text-xs">
                {tag}
              </span>
            ))}
          </div>
          <div className="mt-2">
            <CopyButton value={(result.tags || []).join(', ')} label="Copy tags" size="xs" variant="ghost" />
          </div>
        </div>

        {chapters.length > 0 && (
          <div>
            <h3 className="mb-1">Chapters</h3>
            <ul className="space-y-0.5 text-sm">
              {chapters.map((chapter, index) => (
                <li key={`${chapter.timestamp}-${index}`} className="mono">
                  <span className="text-muted">{chapter.timestamp}</span> {chapter.title}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div>
          <h3 className="mb-1">Improvement suggestions</h3>
          <ul className="list-inside list-disc space-y-0.5 text-sm">
            {asList(result.improvement_suggestions).map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>

        <div>
          <h3 className="mb-1">Thumbnail prompt</h3>
          <p className="rounded-md border border-border bg-surface-2 p-3 text-sm">
            {result.thumbnail_prompt}
          </p>
          <div className="mt-2">
            <CopyButton value={result.thumbnail_prompt} label="Copy prompt" size="xs" variant="ghost" />
          </div>
        </div>
      </CardBody>
      <CardFooter>
        <span className="text-xs text-muted">
          {job?.original_filename} ·{' '}
          {job?.video_duration_seconds ? formatTimestamp(job.video_duration_seconds) : 'duration unknown'}
        </span>
        <span className="inline-flex items-center gap-1.5 text-xs text-muted">
          <Copy className="h-3.5 w-3.5" aria-hidden="true" />
          Copy and paste straight into YouTube Studio
        </span>
      </CardFooter>
    </Card>
  );
}

export default SeoOutputView;
