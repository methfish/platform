import { create } from 'zustand';
import { TradingMode } from '../types/risk';

export interface Notification {
  id: string;
  type: 'info' | 'success' | 'warning' | 'error';
  title: string;
  message: string;
  timestamp: number;
}

interface AppState {
  // Auth
  token: string | null;
  username: string | null;
  isAuthenticated: boolean;
  setAuth: (token: string, username: string) => void;
  clearAuth: () => void;

  // App state
  tradingMode: TradingMode;
  killSwitchActive: boolean;
  setTradingMode: (mode: TradingMode) => void;
  setKillSwitchActive: (active: boolean) => void;

  // Notifications
  notifications: Notification[];
  addNotification: (notification: Omit<Notification, 'id' | 'timestamp'>) => void;
  removeNotification: (id: string) => void;
  clearNotifications: () => void;

  // Sidebar
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  // Auth
  token: localStorage.getItem('pensy_token'),
  username: localStorage.getItem('pensy_username'),
  isAuthenticated: !!localStorage.getItem('pensy_token'),

  setAuth: (token: string, username: string) => {
    localStorage.setItem('pensy_token', token);
    localStorage.setItem('pensy_username', username);
    set({ token, username, isAuthenticated: true });
  },

  clearAuth: () => {
    localStorage.removeItem('pensy_token');
    localStorage.removeItem('pensy_username');
    set({ token: null, username: null, isAuthenticated: false });
  },

  // App state
  tradingMode: 'paper',
  killSwitchActive: false,

  setTradingMode: (mode: TradingMode) => set({ tradingMode: mode }),
  setKillSwitchActive: (active: boolean) => set({ killSwitchActive: active }),

  // Notifications
  notifications: [],

  addNotification: (notification) =>
    set((state) => ({
      notifications: [
        ...state.notifications,
        {
          ...notification,
          id: crypto.randomUUID(),
          timestamp: Date.now(),
        },
      ].slice(-50),
    })),

  removeNotification: (id: string) =>
    set((state) => ({
      notifications: state.notifications.filter((n) => n.id !== id),
    })),

  clearNotifications: () => set({ notifications: [] }),

  // Sidebar
  sidebarCollapsed: false,
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
}));
