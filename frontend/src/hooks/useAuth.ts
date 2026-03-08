import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppStore } from '../store';
import { login as apiLogin } from '../api/admin';

export function useAuth() {
  const navigate = useNavigate();
  const { isAuthenticated, username, setAuth, clearAuth, addNotification } = useAppStore();

  const login = useCallback(
    async (usernameInput: string, password: string) => {
      try {
        const response = await apiLogin(usernameInput, password);
        setAuth(response.access_token, usernameInput);
        addNotification({
          type: 'success',
          title: 'Logged In',
          message: `Welcome back, ${usernameInput}`,
        });
        navigate('/');
      } catch (error: unknown) {
        const message =
          error instanceof Error ? error.message : 'Invalid credentials';
        addNotification({
          type: 'error',
          title: 'Login Failed',
          message,
        });
        throw error;
      }
    },
    [setAuth, addNotification, navigate],
  );

  const logout = useCallback(() => {
    clearAuth();
    navigate('/login');
  }, [clearAuth, navigate]);

  return {
    isAuthenticated,
    username,
    login,
    logout,
  };
}
