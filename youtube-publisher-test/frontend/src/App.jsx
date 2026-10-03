import { Routes, Route, Navigate } from 'react-router-dom';
import PublishPage from './pages/PublishPage';

export default function App() {
  return (
    <div className="min-h-screen">
      <Routes>
        <Route path="/publish" element={<PublishPage />} />
        <Route path="*" element={<Navigate to="/publish" replace />} />
      </Routes>
    </div>
  );
}
