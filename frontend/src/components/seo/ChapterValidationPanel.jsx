import { Check, TriangleAlert } from 'lucide-react';

import { chapterCheckLabel } from '../../utils/chapters';
import { cn } from '../../utils/cn';
import { Badge } from '../ui/Badge';

/**
 * Shows the validation report that the backend produced for this result
 * (chapters, timestamps, repairs). It never re-runs AI to validate.
 */
export function ChapterValidationPanel({ validation, chapters = [] }) {
  const report = validation?.chapter_validation || validation || {};
  const checks = report.checks || {};
  const issues = report.issues || [];
  const repairs = report.repairs_applied || [];
  const valid = report.valid;

  const checkEntries = Object.entries(checks);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={valid ? 'success' : 'danger'}>
          {valid ? 'Chapter validation passed' : 'Chapter validation failed'}
        </Badge>
        {chapters.length > 0 && <Badge variant="neutral">{chapters.length} chapters</Badge>}
      </div>

      {checkEntries.length > 0 && (
        <ul className="grid gap-1.5 sm:grid-cols-2">
          {checkEntries.map(([key, passed]) => (
            <li key={key} className="flex items-center gap-2 text-xs">
              {passed ? (
                <Check className="h-3.5 w-3.5 shrink-0 text-success" aria-hidden="true" />
              ) : (
                <TriangleAlert className="h-3.5 w-3.5 shrink-0 text-danger" aria-hidden="true" />
              )}
              <span className={cn(passed ? 'text-muted' : 'text-danger')}>
                {chapterCheckLabel(key)}
              </span>
            </li>
          ))}
        </ul>
      )}

      {issues.length > 0 && (
        <div className="rounded-md border border-danger/30 bg-danger/10 p-2.5">
          <p className="text-xs font-medium text-danger">Issues found</p>
          <ul className="mt-1 list-inside list-disc space-y-0.5 text-xs text-muted">
            {issues.map((issue) => (
              <li key={issue}>{issue}</li>
            ))}
          </ul>
        </div>
      )}

      {repairs.length > 0 && (
        <div className="rounded-md border border-warning/30 bg-warning/10 p-2.5">
          <p className="text-xs font-medium text-warning">Automatic repairs applied</p>
          <ul className="mt-1 list-inside list-disc space-y-0.5 text-xs text-muted">
            {repairs.map((repair) => (
              <li key={repair}>{repair}</li>
            ))}
          </ul>
        </div>
      )}

      {chapters.length > 0 && (
        <div className="rounded-md border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
                <th className="px-3 py-1.5 font-medium">Timestamp</th>
                <th className="px-3 py-1.5 font-medium">Chapter title</th>
              </tr>
            </thead>
            <tbody>
              {chapters.map((chapter, index) => (
                <tr key={`${chapter.timestamp}-${index}`} className="border-b border-border/60 last:border-0">
                  <td className="mono px-3 py-1.5 text-muted">{chapter.timestamp}</td>
                  <td className="px-3 py-1.5">{chapter.title}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default ChapterValidationPanel;
