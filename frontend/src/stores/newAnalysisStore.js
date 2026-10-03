import { create } from 'zustand';

const DEFAULT_SEO_CONTEXT = {
  video_title: '',
  primary_keyword: '',
  secondary_keywords: '',
  target_audience: '',
  content_language: 'auto',
  seo_language: 'auto',
  content_type: 'auto',
  tone: 'auto',
};

/**
 * Temporary form state for the New Analysis page (upload + SEO context).
 * Server truth stays in TanStack Query.
 */
export const useNewAnalysisStore = create((set, get) => ({
  file: null,
  upload: {
    status: 'idle', // idle | uploading | paused | completed | canceled | failed
    percent: 0,
    uploadedBytes: 0,
    sizeBytes: 0,
    bytesPerSecond: 0,
    etaSeconds: null,
    totalParts: 0,
    nextPart: 0,
    sessionId: null,
    error: null,
  },
  resumable: null,
  seoContext: { ...DEFAULT_SEO_CONTEXT },
  selectedModel: '',
  selectedTemplateId: '',
  setFile: (file) => set({ file }),
  clearFile: () => set({ file: null, resumable: null }),
  setUploadProgress: (progress) => set((state) => ({ upload: { ...state.upload, ...progress } })),
  resetUpload: () =>
    set((state) => ({
      upload: { ...state.upload, status: 'idle', percent: 0, uploadedBytes: 0, error: null, sessionId: null },
      resumable: null,
    })),
  setResumable: (resumable) => set({ resumable }),
  setSeoContextField: (field, value) =>
    set((state) => ({ seoContext: { ...state.seoContext, [field]: value } })),
  setSeoContext: (context) => set({ seoContext: { ...DEFAULT_SEO_CONTEXT, ...context } }),
  setSelectedModel: (selectedModel) => set({ selectedModel }),
  setSelectedTemplateId: (selectedTemplateId) => set({ selectedTemplateId }),
  resetForm: () =>
    set({
      file: null,
      resumable: null,
      seoContext: { ...DEFAULT_SEO_CONTEXT },
      selectedModel: '',
      selectedTemplateId: '',
    }),
  seoContextPayload: () => {
    const context = get().seoContext;
    return {
      video_title: context.video_title?.trim() || null,
      primary_keyword: context.primary_keyword?.trim() || null,
      secondary_keywords: (context.secondary_keywords || '')
        .split(',')
        .map((value) => value.trim())
        .filter(Boolean),
      target_audience: context.target_audience?.trim() || null,
      content_language: context.content_language || 'auto',
      seo_language: context.seo_language || 'auto',
      content_type: context.content_type || 'auto',
      tone: context.tone || 'auto',
    };
  },
}));
