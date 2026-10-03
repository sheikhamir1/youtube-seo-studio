/** Maps backend error codes to user-facing messages (never raw stack traces). */

const FRIENDLY_MESSAGES = {
  UPLOAD_SESSION_NOT_FOUND: 'This upload session no longer exists. Start the upload again.',
  UPLOAD_INCOMPLETE: 'The upload is not finished yet.',
  UPLOAD_PART_INVALID: 'That upload part was rejected. Retrying usually fixes this.',
  UPLOAD_SIZE_MISMATCH: 'The uploaded file size does not match the original file.',
  UPLOAD_STORAGE_ERROR: 'The local disk could not store the upload.',
  MEDIA_NOT_FOUND: 'The video file could not be found on disk.',
  MEDIA_INVALID: 'This file could not be read as a video.',
  MEDIA_NO_AUDIO:
    'This video cannot be analyzed because FFmpeg could not detect a supported audio stream.',
  MEDIA_DURATION_UNAVAILABLE: 'The video duration could not be determined.',
  FFMPEG_NOT_FOUND: 'FFmpeg is not installed. Install FFmpeg and ensure it is on PATH.',
  FFMPEG_ERROR: 'FFmpeg processing failed. See the processing log for details.',
  FFPROBE_NOT_FOUND: 'FFprobe is not installed. Install FFmpeg and ensure it is on PATH.',
  JOB_NOT_FOUND: 'This analysis no longer exists.',
  INVALID_JOB_STATE: 'That action is not possible in the current state of this analysis.',
  GEMINI_NOT_CONFIGURED:
    'Gemini API key is not configured. Add GEMINI_API_KEY to your .env file and restart the backend.',
  GEMINI_MODEL_UNSUPPORTED: 'The selected model is not usable for this analysis.',
  GEMINI_AUDIO_UNSUPPORTED: 'Audio input not supported by the selected model.',
  GEMINI_AUTH_ERROR: 'Gemini rejected the API key. Check GEMINI_API_KEY in your .env file.',
  GEMINI_RATE_LIMIT:
    'Gemini rate limit reached. The worker will pace requests automatically; retry if it persists.',
  GEMINI_TRANSIENT_ERROR: 'Gemini is temporarily unavailable. The worker retries automatically.',
  GEMINI_SCHEMA_ERROR: 'Gemini returned data that failed validation. The result was not saved.',
  GEMINI_SAFETY_BLOCK: 'Gemini refused to process this content.',
  PROMPT_TEMPLATE_NOT_FOUND: 'That prompt template no longer exists.',
  PROMPT_TEMPLATE_INVALID: 'The prompt template is invalid.',
  PROMPT_TEMPLATE_VARIABLE_ERROR: 'The prompt template uses an unsupported variable.',
  SEO_VALIDATION_ERROR: 'The generated SEO output did not pass validation.',
  CHAPTER_VALIDATION_ERROR: 'Chapter validation failed for the generated description.',
  DISK_FULL: 'The local disk is full. Free up space and retry.',
  DATABASE_UNAVAILABLE: 'Database unavailable. Check that PostgreSQL is running.',
  INTERNAL_ERROR: 'The backend reported an internal error. Check the backend logs.',
};

export function describeApiError(error) {
  if (!error) {
    return { title: 'Something went wrong', detail: 'No further information was provided.' };
  }
  if (error.code === 'ERR_NETWORK') {
    return {
      title: 'Unable to connect to backend',
      detail:
        'The API is not reachable. Confirm the backend is running (uvicorn or docker compose).',
    };
  }
  const payload = error.response?.data;
  const code = payload?.error?.code;
  const message = payload?.message || error.message;
  return {
    code,
    title: FRIENDLY_MESSAGES[code] || message || 'Request failed',
    detail: payload?.error?.details && typeof payload.error.details === 'string'
      ? payload.error.details
      : undefined,
  };
}

export const isStatus = (error, status) => error?.response?.status === status;
export const errorCode = (error) => error?.response?.data?.error?.code;
