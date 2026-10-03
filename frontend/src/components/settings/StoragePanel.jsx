import { Database, HardDrive, Trash2 } from 'lucide-react';
import { useState } from 'react';

import { runCleanup } from '../../services/api/system';
import { useStorageQuery, useSystemStatusQuery } from '../../queries/system';
import { useToastStore } from '../../stores/toastStore';
import { describeApiError } from '../../utils/errors';
import { formatBytes, formatNumber } from '../../utils/format';
import Alert from '../ui/Alert';
import Button from '../ui/Button';
import { Card, CardBody, CardFooter, CardHeader } from '../ui/Card';
import { ConfirmDialog } from '../ui/ConfirmDialog';
import KeyValue from '../ui/KeyValue';
import ProgressBar from '../ui/ProgressBar';
import { LoadingBlock } from '../ui/Spinner';

/** Local disk usage per artifact type plus the cleanup action. */
export function StoragePanel() {
  const storageQuery = useStorageQuery();
  const statusQuery = useSystemStatusQuery();
  const [confirmCleanup, setConfirmCleanup] = useState(false);
  const [isCleaning, setIsCleaning] = useState(false);
  const pushToast = useToastStore((state) => state.push);

  const storage = storageQuery.data;
  const disk = statusQuery.data?.disk;

  const cleanup = async () => {
    setIsCleaning(true);
    try {
      const result = await runCleanup();
      pushToast({
        variant: 'success',
        title: 'Cleanup finished',
        description: `${result.deleted_files} files removed, ${formatBytes(result.freed_bytes)} freed.`,
      });
      await Promise.all([storageQuery.refetch(), statusQuery.refetch()]);
      setConfirmCleanup(false);
    } catch (error) {
      const { title, detail } = describeApiError(error);
      pushToast({ variant: 'error', title, description: detail });
    } finally {
      setIsCleaning(false);
    }
  };

  return (
    <Card>
      <CardHeader
        icon={HardDrive}
        title="Storage"
        description="Extracted audio, chunks and outputs stay in the local data directory."
      />
      <CardBody className="space-y-4">
        {storageQuery.isLoading && <LoadingBlock label="Measuring storage…" />}

        {storage && (
          <>
            <KeyValue
              columns={2}
              items={[
                { label: 'Analyses on disk', value: formatNumber(storage.jobs), mono: true },
                { label: 'Total used', value: formatBytes(storage.total_bytes), mono: true },
                { label: 'Source videos', value: formatBytes(storage.source_bytes), mono: true },
                { label: 'Extracted audio (FLAC)', value: formatBytes(storage.audio_bytes), mono: true },
                { label: 'Audio chunks', value: formatBytes(storage.chunk_bytes), mono: true },
                { label: 'Outputs (JSON/logs)', value: formatBytes(storage.output_bytes), mono: true },
              ]}
            />
            <p className="mono text-xs text-muted">data dir: {storage.data_dir}</p>

            {disk && (
              <div>
                <div className="flex items-baseline justify-between text-sm">
                  <span className="flex items-center gap-1.5">
                    <Database className="h-3.5 w-3.5" aria-hidden="true" />
                    Disk
                  </span>
                  <span className="mono">
                    {formatBytes(disk.free_bytes)} free of {formatBytes(disk.total_bytes)}
                  </span>
                </div>
                <ProgressBar
                  className="mt-1.5"
                  value={disk.used_percent}
                  variant={disk.used_percent > 90 ? 'danger' : disk.used_percent > 75 ? 'warning' : 'accent'}
                  label="Disk usage"
                />
              </div>
            )}

            {disk && disk.free_bytes < 5 * 1024 ** 3 && (
              <Alert variant="warning" title="Low disk space">
                Long videos need several gigabytes (the original video plus extracted FLAC audio and
                chunks). Free up space before starting a large analysis.
              </Alert>
            )}
          </>
        )}

        {storageQuery.isError && (
          <Alert variant="error" title="Storage information unavailable">
            The backend could not read the data directory.
          </Alert>
        )}
      </CardBody>
      <CardFooter>
        <p className="text-xs text-muted">
          Cleanup removes aborted upload sessions and their orphan directories only - never completed
          analyses.
        </p>
        <Button
          variant="outline"
          size="sm"
          icon={Trash2}
          onClick={() => setConfirmCleanup(true)}
          disabled={isCleaning}
        >
          Run cleanup
        </Button>
      </CardFooter>

      <ConfirmDialog
        isOpen={confirmCleanup}
        onClose={() => setConfirmCleanup(false)}
        onConfirm={cleanup}
        title="Run storage cleanup?"
        message="Aborted or expired upload sessions and empty directories will be deleted. Completed analyses are left untouched."
        confirmLabel="Run cleanup"
        variant="primary"
        isLoading={isCleaning}
      />
    </Card>
  );
}

export default StoragePanel;
