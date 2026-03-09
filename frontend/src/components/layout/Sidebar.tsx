import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  ShoppingCart,
  BarChart3,
  Brain,
  ShieldAlert,
  Bot,
  Settings,
  ChevronLeft,
  ChevronRight,
  Activity,
  FlaskConical,
  Zap,
} from 'lucide-react';
import { useAppStore } from '../../store';

const navItems = [
  { path: '/', label: 'Research Lab', icon: LayoutDashboard },
  { path: '/research', label: 'Backtests', icon: FlaskConical },
  { path: '/strategies', label: 'Strategies', icon: Zap },
  { path: '/orders', label: 'Orders', icon: ShoppingCart },
  { path: '/positions', label: 'Positions', icon: BarChart3 },
  { path: '/risk', label: 'Risk', icon: ShieldAlert },
  { path: '/agents', label: 'Agents', icon: Bot },
  { path: '/admin', label: 'Admin', icon: Settings },
];

export default function Sidebar() {
  const { sidebarCollapsed, toggleSidebar } = useAppStore();

  return (
    <aside
      className={`fixed left-0 top-0 h-full bg-surface-raised border-r border-surface-border flex flex-col transition-all duration-200 z-30 ${
        sidebarCollapsed ? 'w-16' : 'w-56'
      }`}
    >
      {/* Logo */}
      <div className="flex items-center h-14 px-4 border-b border-surface-border">
        <Activity className="h-6 w-6 text-accent shrink-0" />
        {!sidebarCollapsed && (
          <span className="ml-3 text-lg font-bold text-white tracking-tight">Pensy</span>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 space-y-1 px-2">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            end={item.path === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors duration-150 ${
                isActive
                  ? 'bg-accent/15 text-accent-hover'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-surface-overlay'
              } ${sidebarCollapsed ? 'justify-center' : ''}`
            }
            title={sidebarCollapsed ? item.label : undefined}
          >
            <item.icon className="h-5 w-5 shrink-0" />
            {!sidebarCollapsed && <span>{item.label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* Collapse button */}
      <div className="p-2 border-t border-surface-border">
        <button
          onClick={toggleSidebar}
          className="flex items-center justify-center w-full p-2 rounded-lg text-gray-400 hover:text-gray-200 hover:bg-surface-overlay transition-colors"
        >
          {sidebarCollapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
        </button>
      </div>
    </aside>
  );
}
