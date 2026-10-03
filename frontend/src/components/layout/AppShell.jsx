import { Outlet } from 'react-router-dom';

import { ToastViewport } from '../ui/ToastViewport';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';

/** Application frame: sidebar + top bar + routed content. */
export function AppShell() {
  return (
    <div className="flex min-h-screen bg-bg">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-5 sm:px-6 sm:py-6">
          <Outlet />
        </main>
        <footer className="border-t border-border px-4 py-4 text-center text-xs text-muted sm:px-6">
          Runs entirely on your machine. Video files are never uploaded to Gemini - only extracted
          audio chunks are sent.
        </footer>
      </div>
      <ToastViewport />
    </div>
  );
}

export default AppShell;
