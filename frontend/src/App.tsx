import { Routes, Route, Navigate } from 'react-router-dom';
import { useAppStore } from './store';
import MainLayout from './components/layout/MainLayout';
import LoginPage from './pages/LoginPage';
import Dashboard from './pages/Dashboard';
import OrdersPage from './pages/OrdersPage';
import PositionsPage from './pages/PositionsPage';
import StrategiesPage from './pages/StrategiesPage';
import RiskPage from './pages/RiskPage';
import AgentsPage from './pages/AgentsPage';
import AdminPage from './pages/AdminPage';
import ResearchPage from './pages/ResearchPage';
import ChatPage from './pages/ChatPage';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAppStore((s) => s.isAuthenticated);
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="research" element={<ResearchPage />} />
        <Route path="orders" element={<OrdersPage />} />
        <Route path="positions" element={<PositionsPage />} />
        <Route path="strategies" element={<StrategiesPage />} />
        <Route path="risk" element={<RiskPage />} />
        <Route path="backtests" element={<Navigate to="/research" replace />} />
        <Route path="chat" element={<ChatPage />} />
        <Route path="agents" element={<AgentsPage />} />
        <Route path="admin" element={<AdminPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
