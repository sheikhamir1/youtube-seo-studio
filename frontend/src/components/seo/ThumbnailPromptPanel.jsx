import { Image as ImageIcon } from 'lucide-react';

import CopyButton from '../ui/CopyButton';
import { Card, CardBody, CardHeader } from '../ui/Card';

/**
 * The generated thumbnail prompt is text only - this application never calls an
 * image-generation API. The panel is explicit about that.
 */
export function ThumbnailPromptPanel({ prompt }) {
  if (!prompt) return null;

  return (
    <Card>
      <CardHeader
        icon={ImageIcon}
        title="Thumbnail prompt"
        description="Copy this into your own image tool. No image is generated here."
        actions={<CopyButton value={prompt} label="Copy prompt" />}
      />
      <CardBody>
        <p className="whitespace-pre-wrap rounded-md border border-border bg-surface-2 p-3 text-sm">
          {prompt}
        </p>
      </CardBody>
    </Card>
  );
}

export default ThumbnailPromptPanel;
