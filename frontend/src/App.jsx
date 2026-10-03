import { QueryClientProvider } from '@tanstack/react-query';
import { useEffect } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

import AppShell from './components/layout/AppShell';
import ErrorBoundary from './components/layout/ErrorBoundary';
import RequireJob from './components/layout/RequireJob';
import { ROUTES } from './constants';
import DashboardPage from './pages/DashboardPage';
import HistoryPage from './pages/HistoryPage';
import JobDetailPage from './pages/JobDetailPage';
import NewAnalysisPage from './pages/NewAnalysisPage';
import NotFoundPage from './pages/NotFoundPage';
import ProcessingPage from './pages/ProcessingPage';
import PromptTemplateEditorPage from './pages/PromptTemplateEditorPage';
import PromptTemplatesPage from './pages/PromptTemplatesPage';
import PublishPage from './pages/PublishPage';
import SettingsPage from './pages/SettingsPage';
import TimelinePage from './pages/TimelinePage';
import VideoSelectPage from './pages/VideoSelectPage';
import { queryClient } from './queries/queryClient';
import { useThemeStore } from './stores/themeStore';

/** Full route table (mirrors the specification's route list). */
export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path={ROUTES.dashboard} element={<DashboardPage />} />
        <Route path={ROUTES.newAnalysis} element={<NewAnalysisPage />} />
        <Route
          path="/processing/:jobId"
          element={
            <RequireJob>
              <ProcessingPage />
            </RequireJob>
          }
        />
        <Route path={ROUTES.history} element={<HistoryPage />} />
        <Route
          path="/jobs/:jobId"
          element={
            <RequireJob>
              <JobDetailPage />
            </RequireJob>
          }
        />
        <Route
          path="/jobs/:jobId/timeline"
          element={
            <RequireJob>
              <TimelinePage />
            </RequireJob>
          }
        />
        <Route path={ROUTES.promptTemplates} element={<PromptTemplatesPage />} />
        <Route path="/prompt-templates/new" element={<PromptTemplateEditorPage />} />
        <Route path="/prompt-templates/:templateId" element={<PromptTemplateEditorPage />} />
        <Route path={ROUTES.settings} element={<SettingsPage />} />
        <Route
          path={ROUTES.publishYouTube(':jobId')}
          element={
            <RequireJob>
              <PublishPage />
            </RequireJob>
          }
        />
        <Route
          path={ROUTES.publishYouTubeVideos(':jobId')}
          element={
            <RequireJob>
              <VideoSelectPage />
            </RequireJob>
          }
        />
        <Route path="/dashboard" element={<Navigate to={ROUTES.dashboard} replace />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}

export function App() {
  const initTheme = useThemeStore((state) => state.init);

  useEffect(() => {
    initTheme();
  }, [initTheme]);

  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;
