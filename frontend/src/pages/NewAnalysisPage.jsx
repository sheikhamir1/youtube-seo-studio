import { AlertTriangle, Info, Play, RotateCcw } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import SEOContextForm from '../components/upload/SEOContextForm';
import FilePicker from '../components/upload/FilePicker';
import ResumeBanner from '../components/upload/ResumeBanner';
import UploadProgress from '../components/upload/UploadProgress';
import Alert from '../components/ui/Alert';
import Button from '../components/ui/Button';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import PageHeader from '../components/ui/PageHeader';
import Select from '../components/ui/Select';
import { ROUTES, UPLOAD_PART_SIZE_BYTES } from '../constants';
import { usePageTitle } from '../hooks/usePageTitle';
import { usePromptTemplates } from '../hooks/usePromptTemplates';
import { useCreateJobMutation } from '../queries/jobs';
import { useModelsQuery } from '../queries/system';
import { UploadController, clearActiveUpload, loadActiveUpload } from '../services/upload/uploadService';
import { useNewAnalysisStore } from '../stores/newAnalysisStore';
import { useToastStore } from '../stores/toastStore';
import { describeApiError } from '../utils/errors';
import { filenameToTitle, formatBytes } from '../utils/format';

/**
 * Upload + configuration page.
 *
 * The flow is deliberately: pick file → upload in resumable parts → create the
 * job. Nothing is queued until the upload is verified complete by the backend.
 */
export function NewAnalysisPage() {
  usePageTitle('New analysis');
  const navigate = useNavigate();

  const file = useNewAnalysisStore((state) => state.file);
  const setFile = useNewAnalysisStore((state) => state.setFile);
  const clearFile = useNewAnalysisStore((state) => state.clearFile);
  const uploadState = useNewAnalysisStore((state) => state.upload);
  const setUploadProgress = useNewAnalysisStore((state) => state.setUploadProgress);
  const resetUpload = useNewAnalysisStore((state) => state.resetUpload);
  const resumable = useNewAnalysisStore((state) => state.resumable);
  const setResumable = useNewAnalysisStore((state) => state.setResumable);
  const seoContext = useNewAnalysisStore((state) => state.seoContext);
  const setSeoContextField = useNewAnalysisStore((state) => state.setSeoContextField);
  const seoContextPayload = useNewAnalysisStore((state) => state.seoContextPayload);
  const selectedModel = useNewAnalysisStore((state) => state.selectedModel);
  const setSelectedModel = useNewAnalysisStore((state) => state.setSelectedModel);
  const selectedTemplateId = useNewAnalysisStore((state) => state.selectedTemplateId);
  const setSelectedTemplateId = useNewAnalysisStore((state) => state.setSelectedTemplateId);
  const resetForm = useNewAnalysisStore((state) => state.resetForm);

  const [completedSession, setCompletedSession] = useState(null);
  const [isPaused, setIsPaused] = useState(false);
  const [isResuming, setIsResuming] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const requestIdRef = useRef(null);
  const uploadControllerRef = useRef(null);

  const modelsQuery = useModelsQuery();
  const { templates } = usePromptTemplates(selectedTemplateId, setSelectedTemplateId);
  const createJobMutation = useCreateJobMutation();
  const pushToast = useToastStore((state) => state.push);

  // Offer to resume an interrupted upload from a previous session.
  useEffect(() => {
    const stored = loadActiveUpload();
    if (stored?.uploadId) setResumable(stored);
  }, [setResumable]);

  useEffect(() => {
    if (!selectedModel && modelsQuery.data?.default_model) {
      setSelectedModel(modelsQuery.data.default_model);
    }
  }, [modelsQuery.data, selectedModel, setSelectedModel]);

  const modelOptions = useMemo(
    () =>
      (modelsQuery.data?.models || [])
        // Only models that accept audio *and* are enabled in
        // GEMINI_ALLOWED_MODELS can be chosen: anything else would be rejected
        // by the backend, so it must never appear as a selectable option.
        .filter((model) => model.supports_audio && model.is_configured)
        .map((model) => ({
          value: model.id,
          label: `${model.label}${model.is_default ? ' (default)' : ''}`,
        })),
    [modelsQuery.data],
  );

  const templateOptions = useMemo(
    () =>
      templates.map((template) => ({
        value: template.id,
        label: `${template.name}${template.is_default ? ' (default)' : ''}`,
      })),
    [templates],
  );

  const startUpload = async () => {
    if (!file) return;
    resetUpload();
    setCompletedSession(null);
    setIsPaused(false);
    const controller = new UploadController({
      file,
      onProgress: (progress) => {
        setUploadProgress({
          ...progress,
          error: progress.error ? describeApiError(progress.error).title : null,
        });
        if (progress.status === 'paused') setIsPaused(true);
        if (progress.status === 'uploading') setIsPaused(false);
      },
      onSession: (session) => {
        if (session?.status === 'COMPLETED') setCompletedSession(session);
      },
    });
    uploadControllerRef.current = controller;
    try {
      const outcome = await controller.start();
      if (outcome?.status === 'completed') {
        setIsPaused(false);
        if (!seoContext.video_title) setSeoContextField('video_title', filenameToTitle(file.name));
      }
    } catch (error) {
      const { title, detail } = describeApiError(error);
      pushToast({ variant: 'error', title, description: detail });
    }
  };

  const resumeStoredUpload = async () => {
    if (!file || !resumable?.uploadId) return;
    setIsResuming(true);
    const controller = new UploadController({
      file,
      onProgress: (progress) => setUploadProgress({ ...progress }),
      onSession: (session) => {
        if (session?.status === 'COMPLETED') setCompletedSession(session);
      },
    });
    uploadControllerRef.current = controller;
    try {
      await controller.resume(resumable.uploadId);
      setResumable(null);
    } catch (error) {
      const { title, detail } = describeApiError(error);
      pushToast({ variant: 'error', title, description: detail });
    } finally {
      setIsResuming(false);
    }
  };

  const pauseUpload = () => {
    uploadControllerRef.current?.pause();
    setIsPaused(true);
  };

  const resumeUpload = async () => {
    await uploadControllerRef.current?.resumeUpload();
    setIsPaused(false);
  };

  const cancelUpload = async () => {
    await uploadControllerRef.current?.cancel();
    setIsPaused(false);
    setCompletedSession(null);
    resetUpload();
    pushToast({ variant: 'info', title: 'Upload canceled', description: 'Nothing was queued.' });
  };

  const submit = async () => {
    if (!completedSession?.id) return;
    setIsSubmitting(true);
    // A stable id makes double-clicks and retries idempotent on the backend.
    if (!requestIdRef.current) {
      requestIdRef.current = `${completedSession.id}:${Date.now()}`;
    }
    try {
      const response = await createJobMutation.mutateAsync({
        upload_id: completedSession.id,
        selected_model: selectedModel,
        prompt_template_id: selectedTemplateId,
        seo_context: seoContextPayload(),
        client_request_id: requestIdRef.current,
      });
      const job = response?.data;
      pushToast({
        variant: 'success',
        title: response?.message || 'Analysis queued',
        description: 'The worker picks it up immediately.',
      });
      resetForm();
      clearActiveUpload();
      navigate(ROUTES.processing(job.id));
    } catch (error) {
      const { title, detail } = describeApiError(error);
      pushToast({ variant: 'error', title, description: detail });
    } finally {
      setIsSubmitting(false);
    }
  };

  const uploadComplete = uploadState.status === 'completed' && completedSession;
  const uploading = ['uploading', 'paused'].includes(uploadState.status);
  const canStart = Boolean(file) && !uploading && !uploadComplete;
  const canSubmit = Boolean(uploadComplete) && Boolean(selectedModel) && Boolean(selectedTemplateId);

  return (
    <div className="space-y-5">
      <PageHeader
        title="New analysis"
        description="Pick a long-form video, optionally describe the content, and the pipeline runs locally: FFprobe → FFmpeg → chunking → Gemini Map (one request at a time) → Reduce → validated SEO."
      />

      {resumable && !uploading && !uploadComplete && (
        <ResumeBanner
          session={resumable}
          onResume={resumeStoredUpload}
          isResuming={isResuming}
          onDiscard={() => {
            clearActiveUpload();
            setResumable(null);
          }}
        />
      )}

      <div className="grid gap-4 lg:grid-cols-[3fr_2fr]">
        <div className="space-y-4">
          <Card>
            <CardHeader
              title="1. Video file"
              description={`Uploaded in ${formatBytes(UPLOAD_PART_SIZE_BYTES)} parts with resume support.`}
            />
            <CardBody className="space-y-4">
              <FilePicker
                file={file}
                onSelect={(candidate) => {
                  setFile(candidate);
                  setCompletedSession(null);
                  if (!seoContext.video_title) {
                    setSeoContextField('video_title', filenameToTitle(candidate.name));
                  }
                }}
                onClear={() => {
                  clearFile();
                  resetUpload();
                  setCompletedSession(null);
                }}
                disabled={uploading}
              />

              {uploading && (
                <UploadProgress
                  progress={uploadState}
                  isPaused={isPaused}
                  onPause={pauseUpload}
                  onResume={resumeUpload}
                  onCancel={cancelUpload}
                  onRetry={startUpload}
                />
              )}

              {uploadState.status === 'failed' && (
                <UploadProgress progress={uploadState} onRetry={startUpload} onCancel={cancelUpload} />
              )}

              {uploadComplete && (
                <Alert variant="success" title="Upload verified">
                  <p>
                    {formatBytes(completedSession.expected_size)} received in {completedSession.total_parts}{' '}
                    parts. The backend confirmed the size before accepting it.
                  </p>
                </Alert>
              )}

              {canStart && (
                <Button variant="primary" icon={Play} onClick={startUpload}>
                  Upload video
                </Button>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="2. SEO context (optional)"
              description="Everything here is optional, but it improves the Reduce phase noticeably."
            />
            <CardBody>
              <SEOContextForm value={seoContext} onChange={setSeoContextField} disabled={uploading} />
            </CardBody>
          </Card>
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader title="3. Model & template" description="Both are frozen into the job." />
            <CardBody className="space-y-4">
              <Select
                label="Gemini model"
                options={modelOptions}
                value={selectedModel}
                placeholder={modelsQuery.isLoading ? 'Loading models…' : 'Choose a model'}
                onChange={(event) => setSelectedModel(event.target.value)}
                disabled={modelsQuery.isLoading || uploading}
                hint="Only models that accept audio input are listed."
              />
              <Select
                label="Prompt template"
                options={templateOptions}
                value={selectedTemplateId}
                placeholder={templates.length ? 'Choose a template' : 'No templates available'}
                onChange={(event) => setSelectedTemplateId(event.target.value)}
                disabled={uploading}
                hint="Controls the Reduce prompt. Create your own under Templates."
              />
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Start" description="Nothing runs until you press this." />
            <CardBody className="space-y-3">
              <Button
                variant="primary"
                size="lg"
                fullWidth
                icon={Play}
                disabled={!canSubmit}
                isLoading={isSubmitting}
                onClick={submit}
              >
                {isSubmitting ? 'Queueing…' : 'Start analysis'}
              </Button>

              {!uploadComplete && (
                <p className="flex items-start gap-1.5 text-xs text-muted">
                  <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                  The analysis can start once the upload finishes. Uploads can be paused or resumed without
                  re-sending parts.
                </p>
              )}

              {uploadComplete && (!selectedModel || !selectedTemplateId) && (
                <p className="flex items-start gap-1.5 text-xs text-warning">
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                  Choose a model and a prompt template.
                </p>
              )}

              {uploadState.status === 'canceled' && (
                <Button variant="outline" size="sm" icon={RotateCcw} onClick={startUpload}>
                  Restart upload
                </Button>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="What happens next" />
            <CardBody>
              <ol className="space-y-1.5 text-sm text-muted">
                <li>1. FFprobe validates the file and finds the audio stream.</li>
                <li>2. FFmpeg extracts FLAC audio (mono, 16 kHz) locally.</li>
                <li>3. Audio is chunked into 60-minute overlapping windows.</li>
                <li>4. Each chunk is mapped by Gemini - one request at a time.</li>
                <li>5. Timestamps are rebased onto the video timeline and deduplicated.</li>
                <li>6. One Reduce call produces the SEO metadata, which is validated before saving.</li>
              </ol>
              <p className="mt-3 text-xs text-muted">
                Entirely local. The original video is never uploaded to Gemini, and processing can be
                cancelled at any point without losing completed chunks.
              </p>
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  );
}

export default NewAnalysisPage;
