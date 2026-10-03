/**
 * Product constants. Renaming the product is a one-line change here.
 */
export const PRODUCT_NAME = import.meta.env.VITE_PRODUCT_NAME || 'YouTube SEO Studio';
export const PRODUCT_TAGLINE = 'Local-first AI YouTube SEO for long-form video';

export const ROUTES = {
  dashboard: '/',
  newAnalysis: '/new-analysis',
  processing: (jobId) => `/processing/${jobId}`,
  history: '/history',
  job: (jobId) => `/jobs/${jobId}`,
  publishYouTube: (jobId) => `/jobs/${jobId}/publish-youtube`,
  publishYouTubeVideos: (jobId) => `/jobs/${jobId}/publish-youtube/videos`,
  timeline: (jobId) => `/jobs/${jobId}/timeline`,
  promptTemplates: '/prompt-templates',
  newPromptTemplate: '/prompt-templates/new',
  promptTemplate: (templateId) => `/prompt-templates/${templateId}`,
  settings: '/settings',
};

export const NAV_ITEMS = [
  { to: ROUTES.dashboard, label: 'Dashboard', icon: 'layout-dashboard' },
  { to: ROUTES.newAnalysis, label: 'New Analysis', icon: 'plus-circle' },
  { to: ROUTES.history, label: 'History', icon: 'history' },
  { to: ROUTES.promptTemplates, label: 'Templates', icon: 'file-text' },
  { to: ROUTES.settings, label: 'Settings', icon: 'settings' },
];

export const QUERY_KEYS = {
  jobs: (params) => ['jobs', params],
  job: (jobId) => ['job', jobId],
  jobSummary: (jobId) => ['job', jobId, 'summary'],
  jobTimeline: (jobId) => ['job', jobId, 'timeline'],
  jobEvents: (jobId, params) => ['job', jobId, 'events', params],
  jobChunks: (jobId) => ['job', jobId, 'chunks'],
  jobResults: (jobId) => ['job', jobId, 'results'],
  currentResult: (jobId) => ['job', jobId, 'results', 'current'],
  templates: ['prompt-templates'],
  template: (id) => ['prompt-templates', id],
  templateVariables: ['prompt-templates', 'variables'],
  systemStatus: ['system', 'status'],
  systemModels: ['system', 'models'],
  systemQuota: ['system', 'quota'],
  systemStorage: ['system', 'storage'],
};

export const JOB_STATUS = {
  QUEUED: 'QUEUED',
  VALIDATING: 'VALIDATING',
  EXTRACTING: 'EXTRACTING',
  CHUNKING: 'CHUNKING',
  MAPPING: 'MAPPING',
  REDUCING: 'REDUCING',
  COMPLETED: 'COMPLETED',
  FAILED: 'FAILED',
  CANCEL_REQUESTED: 'CANCEL_REQUESTED',
  CANCELED: 'CANCELED',
};

export const ACTIVE_STATUSES = [
  JOB_STATUS.VALIDATING,
  JOB_STATUS.EXTRACTING,
  JOB_STATUS.CHUNKING,
  JOB_STATUS.MAPPING,
  JOB_STATUS.REDUCING,
  JOB_STATUS.CANCEL_REQUESTED,
];

export const isActiveStatus = (status) => ACTIVE_STATUSES.includes(status);
export const isTerminalStatus = (status) =>
  [JOB_STATUS.COMPLETED, JOB_STATUS.FAILED, JOB_STATUS.CANCELED].includes(status);

/** Pipeline stages shown on the processing page, in order. */
export const PIPELINE_STAGES = [
  { key: 'UPLOAD', label: 'Upload', statuses: [], weight: 0 },
  { key: 'VALIDATION', label: 'Validation', statuses: [JOB_STATUS.VALIDATING] },
  { key: 'EXTRACTION', label: 'Audio Extraction', statuses: [JOB_STATUS.EXTRACTING] },
  { key: 'CHUNKING', label: 'Audio Chunking', statuses: [JOB_STATUS.CHUNKING] },
  { key: 'MAPPING', label: 'AI Mapping', statuses: [JOB_STATUS.MAPPING] },
  { key: 'REDUCTION', label: 'SEO Generation', statuses: [JOB_STATUS.REDUCING] },
  { key: 'COMPLETED', label: 'Completed', statuses: [JOB_STATUS.COMPLETED] },
];

export const HISTORY_FILTERS = [
  { value: '', label: 'All' },
  { value: 'PROCESSING', label: 'Processing' },
  { value: 'COMPLETED', label: 'Completed' },
  { value: 'FAILED', label: 'Failed' },
  { value: 'CANCELED', label: 'Canceled' },
];

export const LANGUAGE_OPTIONS = [
  'auto',
  'English',
  'Hindi',
  'Urdu',
  'Hindi/English',
  'Urdu/English',
  'Hindi/Urdu',
];

export const CONTENT_TYPE_OPTIONS = [
  'auto',
  'Lecture',
  'Course',
  'Podcast',
  'Interview',
  'Tutorial',
  'Webinar',
  'Conference Talk',
  'Documentary',
  'Training Session',
  'Religious Lecture',
];

export const TONE_OPTIONS = [
  'auto',
  'Educational',
  'Conversational',
  'Professional',
  'Inspirational',
  'Technical',
  'Narrative',
];

export const TITLE_MAX_CHARS = 100;
export const DESCRIPTION_MAX_CHARS = 5000;
export const DESCRIPTION_WARNING_CHARS = 4500;
export const UPLOAD_PART_SIZE_BYTES = 32 * 1024 * 1024;
export const UPLOAD_SESSION_STORAGE_KEY = 'yss-active-upload';

export const EVENT_LEVEL_STYLES = {
  INFO: 'text-muted',
  SUCCESS: 'text-success',
  WARNING: 'text-warning',
  ERROR: 'text-danger',
};
