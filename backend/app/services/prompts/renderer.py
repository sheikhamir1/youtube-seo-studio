"""Safe prompt template rendering.

- Jinja2 sandboxed environment (no Python evaluation, no arbitrary attribute access)
- strict undefined variables: a missing variable is a hard error, never ""
- unknown variables are rejected during validation before any Gemini call
"""

from __future__ import annotations

import json
from typing import Any

from jinja2 import StrictUndefined, TemplateSyntaxError, UndefinedError, meta
from jinja2.sandbox import SandboxedEnvironment

from app.core.errors import ErrorCode, PromptTemplateError
from app.services.prompts.defaults import SUPPORTED_TEMPLATE_VARIABLES

_ENV = SandboxedEnvironment(undefined=StrictUndefined, autoescape=False, trim_blocks=False)


def extract_template_variables(template: str) -> set[str]:
    """Return the set of top-level variables referenced by a template."""
    try:
        parsed = _ENV.parse(template)
    except TemplateSyntaxError as exc:
        raise PromptTemplateError(
            "The prompt template contains a syntax error.",
            details={"line": exc.lineno, "error": exc.message},
            code=ErrorCode.PROMPT_TEMPLATE_INVALID,
        ) from exc
    return set(meta.find_undeclared_variables(parsed))


def validate_template_variables(template: str) -> set[str]:
    """Fail early when a template references an unsupported variable."""
    used = extract_template_variables(template)
    unknown = sorted(used - set(SUPPORTED_TEMPLATE_VARIABLES))
    if unknown:
        raise PromptTemplateError(
            "The prompt template references unsupported variables: " + ", ".join(unknown),
            details={
                "unknown_variables": unknown,
                "available_variables": list(SUPPORTED_TEMPLATE_VARIABLES),
            },
            code=ErrorCode.PROMPT_TEMPLATE_VARIABLE_ERROR,
        )
    return used


def render_template(template: str, context: dict[str, Any]) -> str:
    """Render a template with strict variables. Raises PromptTemplateError."""
    validate_template_variables(template)
    missing = sorted(set(extract_template_variables(template)) - set(context))
    if missing:
        # Unknown variables must never silently become empty strings.
        raise PromptTemplateError(
            "Missing values for template variables: " + ", ".join(missing),
            details={"missing_variables": missing},
            code=ErrorCode.PROMPT_TEMPLATE_VARIABLE_ERROR,
        )
    try:
        return _ENV.from_string(template).render(**context)
    except UndefinedError as exc:
        raise PromptTemplateError(
            "Template rendering error: a required variable is undefined.",
            details=str(exc),
            code=ErrorCode.PROMPT_TEMPLATE_VARIABLE_ERROR,
        ) from exc
    except TemplateSyntaxError as exc:
        raise PromptTemplateError(
            "Template rendering error: invalid template syntax.",
            details={"line": exc.lineno, "error": exc.message},
            code=ErrorCode.PROMPT_TEMPLATE_INVALID,
        ) from exc


def build_seo_context_values(
    *,
    seo_context: dict[str, Any],
    original_filename: str,
    video_duration_seconds: float | None,
    timeline: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the variable values for the Reduce template.

    ``timeline_text`` is a compact human-readable form; ``timeline_json`` is the
    structured form the model is instructed to rely on.
    """
    from app.core.timeutils import format_duration, format_timestamp

    title = (seo_context.get("video_title") or "").strip() or _filename_to_title(original_filename)
    secondary = seo_context.get("secondary_keywords") or []
    if isinstance(secondary, str):
        secondary = [part.strip() for part in secondary.split(",") if part.strip()]

    timeline_lines = []
    for topic in timeline:
        start = format_timestamp(float(topic.get("start_seconds", 0)))
        end = format_timestamp(float(topic.get("end_seconds", 0)))
        timeline_lines.append(f"- [{start} - {end}] {topic.get('topic', '')}: {topic.get('summary', '')}")

    return {
        "video_title": title,
        "video_duration_seconds": int(video_duration_seconds) if video_duration_seconds else 0,
        "video_duration_formatted": format_duration(video_duration_seconds),
        "primary_keyword": (seo_context.get("primary_keyword") or "").strip() or "(not provided)",
        "secondary_keywords": ", ".join(secondary) if secondary else "(not provided)",
        "target_audience": (seo_context.get("target_audience") or "").strip() or "(not provided)",
        "content_language": seo_context.get("content_language") or "auto",
        "seo_language": seo_context.get("seo_language") or "auto",
        "content_type": seo_context.get("content_type") or "auto",
        "tone": seo_context.get("tone") or "auto",
        "timeline_json": json.dumps(timeline, ensure_ascii=False, indent=2),
        "timeline_text": "\n".join(timeline_lines) if timeline_lines else "(empty timeline)",
    }


def _filename_to_title(filename: str) -> str:
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    cleaned = stem.replace("_", " ").replace("-", " ").strip()
    return cleaned[:200] or "Untitled video"


def build_reduce_prompts(
    *,
    template_system_prompt: str,
    template_user_prompt: str,
    context: dict[str, Any],
) -> tuple[str, str]:
    """Assemble the final Reduce prompts (platform + template layers)."""
    from app.services.prompts.defaults import REDUCE_PLATFORM_INSTRUCTIONS

    validate_template_variables(template_user_prompt)
    rendered_user = render_template(template_user_prompt, context)
    system_prompt = "\n\n".join(
        part for part in (REDUCE_PLATFORM_INSTRUCTIONS, template_system_prompt.strip()) if part
    )
    return system_prompt, rendered_user
