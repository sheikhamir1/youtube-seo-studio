import {
  CONTENT_TYPE_OPTIONS,
  LANGUAGE_OPTIONS,
  TONE_OPTIONS,
} from '../../constants';
import Input from '../ui/Input';
import Select from '../ui/Select';

/**
 * Optional SEO context. Every field is optional; the pipeline works without it,
 * but filled-in context measurably improves the Reduce phase output.
 */
export function SEOContextForm({ value, onChange, disabled = false }) {
  const set = (field) => (event) => onChange(field, event.target.value);

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Input
        label="Working video title (optional)"
        hint="Used as context for the AI. The final title is generated in the Reduce phase."
        placeholder="e.g. Advanced RAG Course - Session 4"
        value={value.video_title}
        onChange={set('video_title')}
        disabled={disabled}
        maxLength={300}
      />
      <Input
        label="Primary keyword (optional)"
        placeholder="e.g. vector search"
        value={value.primary_keyword}
        onChange={set('primary_keyword')}
        disabled={disabled}
        maxLength={200}
      />
      <Input
        label="Secondary keywords (optional)"
        hint="Comma separated."
        placeholder="embeddings, semantic search"
        value={value.secondary_keywords}
        onChange={set('secondary_keywords')}
        disabled={disabled}
      />
      <Input
        label="Target audience (optional)"
        placeholder="e.g. Developers learning retrieval systems"
        value={value.target_audience}
        onChange={set('target_audience')}
        disabled={disabled}
        maxLength={300}
      />
      <Select
        label="Content language"
        options={LANGUAGE_OPTIONS}
        value={value.content_language}
        onChange={set('content_language')}
        disabled={disabled}
      />
      <Select
        label="SEO output language"
        options={LANGUAGE_OPTIONS}
        value={value.seo_language}
        onChange={set('seo_language')}
        disabled={disabled}
      />
      <Select
        label="Content type"
        options={CONTENT_TYPE_OPTIONS}
        value={value.content_type}
        onChange={set('content_type')}
        disabled={disabled}
      />
      <Select
        label="Tone"
        options={TONE_OPTIONS}
        value={value.tone}
        onChange={set('tone')}
        disabled={disabled}
      />
    </div>
  );
}

export default SEOContextForm;
