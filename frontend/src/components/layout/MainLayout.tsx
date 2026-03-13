import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';
import { useAppStore } from '../../store';

export default function MainLayout() {
  const sidebarCollapsed = useAppStore((s) => s.sidebarCollapsed);

  return (
    <div className="min-h-screen bg-surface flex">
      <Sidebar />
      <div
        className={`flex-1 flex flex-col transition-all duration-200 ${
          sidebarCollapsed ? 'ml-16' : 'ml-56'
        }`}
      >
        <Header />
        <main className="flex-1 p-6 overflow-y-auto min-w-0">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
