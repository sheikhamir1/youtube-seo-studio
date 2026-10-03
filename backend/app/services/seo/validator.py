"""SEOValidator: application validation of Gemini's Reduce output.

Trust model: model output -> Pydantic schema -> business validation ->
YouTube-compatible validation -> database. The model is never trusted.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.constants import (
    DESCRIPTION_MAX_CHARS,
    DESCRIPTION_WARNING_CHARS,
    MAX_TAGS,
    SEO_SCORE_MAX,
    TAG_MAX_CHARS,
    TITLE_MAX_CHARS,
)
from app.core.errors import ErrorCode, SEOValidationError
from app.schemas.seo import SEOOutput
from app.services.seo.chapters import repair_description_chapters, validate_chapters

_URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)


class SEOValidator:
    """Validates and (where safe) repairs the structured SEO output."""

    def __init__(
        self,
        *,
        video_duration_seconds: float | None = None,
        allowed_chapter_timestamps: list[float] | None = None,
        allowed_chapter_windows: list[tuple[float, float]] | None = None,
    ) -> None:
        self.video_duration_seconds = video_duration_seconds
        self.allowed_chapter_timestamps = allowed_chapter_timestamps
        self.allowed_chapter_windows = allowed_chapter_windows

    def validate(self, payload: dict[str, Any]) -> tuple[SEOOutput, dict[str, Any]]:
        """Return (validated output, validation metadata). Raises SEOValidationError."""
        try:
            output = SEOOutput.model_validate(payload)
        except Exception as exc:  # pydantic ValidationError
            raise SEOValidationError(
                "The generated SEO output failed schema validation.",
                details=str(exc)[:1500],
                code=ErrorCode.SEO_VALIDATION_ERROR,
            ) from exc

        errors: list[str] = []
        warnings: list[str] = []
        repairs: list[str] = []

        # ---------------------------------------------------------------- title
        title = output.title.strip()
        if len(title) > TITLE_MAX_CHARS:
            errors.append(f"Title is {len(title)} characters; the maximum is {TITLE_MAX_CHARS}.")

        # ---------------------------------------------------------- description
        description, chapter_repairs = repair_description_chapters(output.description)
        repairs.extend(chapter_repairs)
        if len(description) > DESCRIPTION_MAX_CHARS:
            errors.append(
                f"Description is {len(description)} characters; the maximum is {DESCRIPTION_MAX_CHARS}."
            )
        elif len(description) > DESCRIPTION_WARNING_CHARS:
            warnings.append("Description is close to the 5,000 character limit.")

        # ----------------------------------------------------------------- tags
        tags = self._validate_tags(output.tags, errors, warnings)

        # ---------------------------------------------------------------- score
        if not 0 <= output.seo_score <= SEO_SCORE_MAX:
            errors.append(f"seo_score must be between 0 and {SEO_SCORE_MAX}.")

        # ------------------------------------------------------------- chapters
        chapter_report = validate_chapters(
            description,
            video_duration_seconds=self.video_duration_seconds,
            allowed_timestamps=self.allowed_chapter_timestamps,
            allowed_windows=self.allowed_chapter_windows,
        )
        if not chapter_report["valid"]:
            errors.extend(chapter_report["issues"])

        # ------------------------------------------------------- thumbnail text
        if len(output.thumbnail_prompt.strip()) < 40:
            warnings.append("The thumbnail prompt is very short; a richer prompt is more useful.")

        # ------------------------------------------------------- fabricated URLs
        urls = _URL_PATTERN.findall(description)
        if urls:
            warnings.append(
                "The description contains URLs. Verify they were supplied by you: " + ", ".join(urls[:3])
            )

        metadata = {
            "title_length": len(title),
            "description_length": len(description),
            "tag_count": len(tags),
            "chapter_validation": {
                "valid": chapter_report["valid"],
                "checks": chapter_report["checks"],
                "issues": chapter_report["issues"],
                "count": len(chapter_report["chapters"]),
            },
            "warnings": warnings,
            "repairs": repairs,
            "errors": errors,
            "validated_by": "application",
        }

        if errors:
            raise SEOValidationError(
                "The generated SEO output is not valid: " + " ".join(errors[:3]),
                details=metadata,
                code=ErrorCode.SEO_VALIDATION_ERROR,
            )

        cleaned = SEOOutput(
            title=title,
            description=description,
            tags=tags,
            seo_score=int(output.seo_score),
            improvement_suggestions=output.improvement_suggestions.strip(),
            thumbnail_prompt=output.thumbnail_prompt.strip(),
        )
        return cleaned, metadata

    # -------------------------------------------------------------- helpers
    @staticmethod
    def _validate_tags(tags: list[str], errors: list[str], warnings: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for tag in tags:
            text = (tag or "").strip().lstrip("#").strip()
            if not text:
                continue
            if len(text) > TAG_MAX_CHARS:
                warnings.append(f"Tag '{text[:30]}...' is longer than {TAG_MAX_CHARS} characters.")
                text = text[:TAG_MAX_CHARS].strip()
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(text)
        if not cleaned:
            errors.append("At least one tag is required.")
        if len(cleaned) > MAX_TAGS:
            warnings.append(f"More than {MAX_TAGS} tags were provided; extra tags were dropped.")
            cleaned = cleaned[:MAX_TAGS]
        return cleaned


def validate_manual_edit(payload: dict[str, Any]) -> tuple[SEOOutput, dict[str, Any]]:
    """Validate a manual (user) edit before saving. Never calls Gemini."""
    validator = SEOValidator()
    return validator.validate({**payload, "seo_score": payload.get("seo_score", 0)})
