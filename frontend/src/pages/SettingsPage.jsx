import { RefreshCw } from 'lucide-react';
import { useMemo, useState } from 'react';

import DependencyChecklist from '../components/settings/DependencyChecklist';
import ModelSelector from '../components/settings/ModelSelector';
import ProcessingDefaults from '../components/settings/ProcessingDefaults';
import QuotaPanel from '../components/settings/QuotaPanel';
import StoragePanel from '../components/settings/StoragePanel';
import ThemePanel from '../components/settings/ThemePanel';
import Alert from '../components/ui/Alert';
import Button from '../components/ui/Button';
import { Card, CardBody, CardHeader } from '../components/ui/Card';
import KeyValue from '../components/ui/KeyValue';
import PageHeader from '../components/ui/PageHeader';
import { PRODUCT_NAME } from '../constants';
import { usePageTitle } from '../hooks/usePageTitle';
import { useJobsQuery } from '../queries/jobs';
import { useModelsQuery, useQuotaQuery, useSystemStatusQuery } from '../queries/system';
import { formatDateTime } from '../utils/format';

/**
 * Settings is a *status* page: the pipeline configuration lives in `.env` by
 * design, so nothing here pretends to change server behaviour.
 */
export function SettingsPage() {
  usePageTitle('Settings');

  const statusQuery = useSystemStatusQuery();
  const modelsQuery = useModelsQuery();
  const quotaQuery = useQuotaQuery();
  const jobsQuery = useJobsQuery({ page: 1, pageSize: 1 });
  const [preferredModel, setPreferredModel] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  const status = statusQuery.data;
  const selectedModel = preferredModel || status?.default_model || '';
  const recentJob = useMemo(() => jobsQuery.data?.items?.[0] || null, [jobsQuery.data]);

  const refreshAll = async () => {
    setRefreshing(true);
    await Promise.all([statusQuery.refetch(), modelsQuery.refetch(), quotaQuery.refetch()]);
    setRefreshing(false);
  };

  return (
    <div className="space-y-5">
      <PageHeader
        title="Settings"
        description={`Runtime status for ${PRODUCT_NAME}. Pipeline limits and the Gemini key come from the backend environment file, so there is nothing to configure in the browser.`}
        actions={
          <Button variant="outline" icon={RefreshCw} isLoading={refreshing} onClick={refreshAll}>
            Re-check
          </Button>
        }
      />

      {statusQuery.isError && (
        <Alert variant="error" title="Backend unreachable">
          Start the API (<code className="mono">uvicorn app.main:app --port 8000</code>) or run{' '}
          <code className="mono">docker compose up</code>, then press Re-check.
        </Alert>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <DependencyChecklist status={status} isLoading={statusQuery.isLoading} />

        <Card>
          <CardHeader title="Environment" description="Read from the backend configuration." />
          <CardBody>
            <KeyValue
              columns={1}
              items={[
                { label: 'Application', value: status?.app_name || PRODUCT_NAME },
                { label: 'Environment', value: status?.app_env || '—', mono: true },
                { label: 'AI provider', value: status?.ai_provider || '—', mono: true },
                { label: 'Default model', value: status?.default_model || '—', mono: true },
                { label: 'Data directory', value: status?.data_dir || '—', mono: true },
                {
                  label: 'Worker',
                  value: status
                    ? `${status.worker?.worker_id || 'none'} · ${
                        status.worker?.alive ? 'alive' : 'not running'
                      }`
                    : '—',
                },
                {
                  label: 'Worker heartbeat',
                  value:
                    status?.worker?.heartbeat_age_seconds !== null &&
                    status?.worker?.heartbeat_age_seconds !== undefined
                      ? `${Math.round(status.worker.heartbeat_age_seconds)}s ago`
                      : '—',
                  mono: true,
                },
                {
                  label: 'Queued / active jobs',
                  value: status ? `${status.queued_jobs} / ${status.active_jobs}` : '—',
                  mono: true,
                },
                ...(status?.worker?.last_heartbeat_at
                  ? [{ label: 'Last heartbeat', value: formatDateTime(status.worker.last_heartbeat_at) }]
                  : []),
              ]}
            />
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Model registry"
            description="Pick the model used for new analyses (stored per job, not globally)."
          />
          <CardBody>
            <ModelSelector
              models={modelsQuery.data?.models || []}
              value={selectedModel}
              onChange={setPreferredModel}
              defaultModel={modelsQuery.data?.default_model}
              isLoading={modelsQuery.isLoading}
            />
            <p className="mt-3 text-xs text-muted">
              Changing the selection here only affects the value pre-filled on the New Analysis page; existing
              analyses keep the model they were created with.
            </p>
          </CardBody>
        </Card>

        <QuotaPanel quota={quotaQuery.data} isLoading={quotaQuery.isLoading} />

        <ProcessingDefaults job={recentJob} isLoading={jobsQuery.isLoading} />

        <ThemePanel />
      </div>

      <StoragePanel />
    </div>
  );
}

export default SettingsPage;
