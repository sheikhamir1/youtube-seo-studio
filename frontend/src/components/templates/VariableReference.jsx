import { Braces } from 'lucide-react';

import CopyButton from '../ui/CopyButton';
import { Card, CardBody, CardHeader } from '../ui/Card';

/**
 * Available template variables, taken from the backend registry so the editor
 * can never suggest a variable that rendering would reject.
 */
export function VariableReference({ variables = [], sampleContext = null, onInsert }) {
  return (
    <Card>
      <CardHeader
        icon={Braces}
        title="Available variables"
        description="Click to insert at the cursor. Unknown variables are rejected before any AI call."
      />
      <CardBody className="space-y-2">
        <ul className="flex flex-wrap gap-1.5">
          {variables.map((variable) => (
            <li key={variable}>
              <button
                type="button"
                onClick={() => onInsert?.(variable)}
                className="mono rounded border border-border bg-surface-2 px-1.5 py-0.5 text-[11px] transition-colors hover:border-accent hover:text-accent"
                title={sampleContext?.[variable] ? String(sampleContext[variable]).slice(0, 160) : variable}
              >
                {`{{ ${variable} }}`}
              </button>
            </li>
          ))}
        </ul>

        {sampleContext && (
          <details className="rounded-md border border-border bg-surface-2 p-2.5">
            <summary className="cursor-pointer text-xs font-medium text-muted">
              Sample values used by Preview
            </summary>
            <dl className="mt-2 space-y-1.5">
              {Object.entries(sampleContext).map(([key, value]) => (
                <div key={key} className="grid grid-cols-[160px_1fr] gap-2 text-xs">
                  <dt className="mono text-muted">{key}</dt>
                  <dd className="min-w-0 break-words">
                    {typeof value === 'string' ? value : JSON.stringify(value)}
                  </dd>
                </div>
              ))}
            </dl>
            <div className="mt-2">
              <CopyButton
                value={JSON.stringify(sampleContext, null, 2)}
                label="Copy sample context"
                size="xs"
                variant="ghost"
              />
            </div>
          </details>
        )}
      </CardBody>
    </Card>
  );
}

export default VariableReference;
