"""Non-tunable / low-level constants shared across modules.

Anything the operator may reasonably want to change lives in
:mod:`app.core.config` (environment) or in the AppSettings database record.
"""

from __future__ import annotations

# --- YouTube platform limits -------------------------------------------------
TITLE_MAX_CHARS = 100
DESCRIPTION_MAX_CHARS = 5000
DESCRIPTION_WARNING_CHARS = 4500
MIN_CHAPTERS_LONG_FORM = 3
MIN_CHAPTER_SPACING_SECONDS = 10.0
MAX_TAGS = 60
TAG_MAX_CHARS = 60

# --- SEO scoring rubric (application-level, *not* a YouTube metric) ----------
SEO_SCORE_WEIGHTS: dict[str, int] = {
    "content_accuracy_and_topic_coverage": 25,
    "title_quality_and_search_intent": 20,
    "description_quality": 20,
    "chapter_usefulness": 15,
    "keyword_relevance_and_natural_integration": 10,
    "tag_relevance": 5,
    "thumbnail_prompt_alignment": 5,
}
SEO_SCORE_MAX = sum(SEO_SCORE_WEIGHTS.values())

# --- Progress model ----------------------------------------------------------
# Stage weights sum to 100; mapping progress uses completed_chunks/total_chunks.
STAGE_WEIGHTS: dict[str, float] = {
    "VALIDATION": 5.0,
    "EXTRACTION": 15.0,
    "CHUNKING": 15.0,
    "MAPPING": 50.0,
    "REDUCTION": 15.0,
}


# --- Retry / backoff ---------------------------------------------------------
BACKOFF_BASE_SECONDS = 2.0
BACKOFF_MAX_SECONDS = 300.0
RETRYABLE_HTTP_STATUSES: frozenset[int] = frozenset({408, 409, 429, 500, 502, 503, 504})
NON_RETRYABLE_HTTP_STATUSES: frozenset[int] = frozenset({400, 401, 403, 404, 422})

# --- Floating point tolerance when clamping model timestamps -----------------
TIMESTAMP_EPSILON_SECONDS = 1.5

# --- Supported content/SEO languages (UI list; backend accepts any string) ---
LANGUAGE_OPTIONS: tuple[str, ...] = (
    "auto",
    "English",
    "Hindi",
    "Urdu",
    "Hindi/English",
    "Urdu/English",
    "Hindi/Urdu",
)

CONTENT_TYPE_OPTIONS: tuple[str, ...] = (
    "auto",
    "Lecture",
    "Course",
    "Podcast",
    "Interview",
    "Tutorial",
    "Webinar",
    "Conference Talk",
    "Documentary",
    "Training Session",
    "Religious Lecture",
)

TONE_OPTIONS: tuple[str, ...] = (
    "auto",
    "Educational",
    "Conversational",
    "Professional",
    "Inspirational",
    "Technical",
    "Narrative",
)
