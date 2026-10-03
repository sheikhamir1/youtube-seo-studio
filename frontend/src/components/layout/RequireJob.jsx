import { Navigate, useParams } from 'react-router-dom';

import { ROUTES } from '../../constants';

/**
 * Guards job-scoped routes: `/jobs/:jobId` requires a non-empty jobId, so a
 * malformed URL redirects to history instead of rendering a broken page.
 */
export function RequireJob({ children }) {
  const { jobId } = useParams();
  if (!jobId || !/^[0-9a-fA-F-]{8,}$/.test(jobId)) {
    return <Navigate to={ROUTES.history} replace />;
  }
  return children;
}

export default RequireJob;
