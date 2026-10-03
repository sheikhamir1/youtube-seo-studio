import { Lightbulb } from 'lucide-react';

import CopyButton from '../ui/CopyButton';
import { Card, CardBody, CardHeader } from '../ui/Card';

/** Model-produced, advisory improvement notes for the current metadata. */
export function ImprovementSuggestions({ suggestions }) {
  if (!suggestions) return null;

  const lines = String(suggestions)
    .split('\n')
    .map((line) => line.replace(/^[-*\d.\s]+/, '').trim())
    .filter(Boolean);

  return (
    <Card>
      <CardHeader
        icon={Lightbulb}
        title="Improvement suggestions"
        description="Advisory only - apply them by editing the fields and saving."
        actions={<CopyButton value={suggestions} label="Copy" />}
      />
      <CardBody>
        {lines.length > 1 ? (
          <ul className="list-inside list-disc space-y-1 text-sm">
            {lines.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        ) : (
          <p className="whitespace-pre-wrap text-sm">{suggestions}</p>
        )}
      </CardBody>
    </Card>
  );
}

export default ImprovementSuggestions;
