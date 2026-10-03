import { Component } from 'react';
import { RefreshCw } from 'lucide-react';

import { Button } from '../ui/Button';

/**
 * Catches render errors so a single broken view cannot blank the whole app
 * (a blank white screen is treated as a bug, not a state).
 */
export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // Logged deliberately: a render failure must be visible in the console.
    console.error('Unhandled render error', error, info);
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div className="mx-auto max-w-xl px-4 py-16">
        <div className="card card-pad">
          <h1 className="text-lg font-semibold">Something broke on this page</h1>
          <p className="mt-2 text-sm text-muted">
            The rest of the application still works. Reload the page, and if this keeps happening
            check the backend logs.
          </p>
          <pre className="mt-3 max-h-40 overflow-auto rounded border border-border bg-surface-2 p-3 text-xs text-muted">
            {String(error?.message || error)}
          </pre>
          <div className="mt-4 flex gap-2">
            <Button icon={RefreshCw} variant="primary" onClick={() => window.location.reload()}>
              Reload page
            </Button>
            <Button variant="outline" onClick={() => this.setState({ error: null })}>
              Try again
            </Button>
          </div>
        </div>
      </div>
    );
  }
}

export default ErrorBoundary;
