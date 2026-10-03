import { Compass } from 'lucide-react';
import { Link } from 'react-router-dom';

import Button from '../components/ui/Button';
import EmptyState from '../components/ui/EmptyState';
import { ROUTES } from '../constants';
import { usePageTitle } from '../hooks/usePageTitle';

export function NotFoundPage() {
  usePageTitle('Page not found');

  return (
    <EmptyState
      icon={Compass}
      title="This page does not exist"
      description="The link may be out of date. Use the navigation to get back on track."
      action={
        <>
          <Link to={ROUTES.dashboard}>
            <Button variant="primary">Go to dashboard</Button>
          </Link>
          <Link to={ROUTES.history} className="ml-2">
            <Button variant="outline">Open history</Button>
          </Link>
        </>
      }
      className="my-16"
    />
  );
}

export default NotFoundPage;
