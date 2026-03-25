/**
 * Auth Store (Zustand)
 * 
 * Client-side authentication state management.
 * Stores current user, tokens, and authentication status.
 */

import { create } from 'zustand';
import { User, AuthToken } from '../types';

interface AuthStore {
  // State
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;

  // Actions
  setAuth: (token: AuthToken) => void;
  setUser: (user: User) => void;
  setAccessToken: (token: string) => void;
  logout: () => void;
  initializeFromLocalStorage: () => void;
}

export const useAuthStore = create<AuthStore>((set) => ({
  user: null,
  accessToken: null,
  refreshToken: null,
  isAuthenticated: false,
  isLoading: false,

  setAuth: (token: AuthToken) => {
    localStorage.setItem('accessToken', token.access_token);
    localStorage.setItem('refreshToken', token.refresh_token);
    localStorage.setItem('user', JSON.stringify(token.user));
    
    set({
      user: token.user,
      accessToken: token.access_token,
      refreshToken: token.refresh_token,
      isAuthenticated: true,
    });
  },

  setUser: (user: User) => {
    localStorage.setItem('user', JSON.stringify(user));
    set({ user });
  },

  setAccessToken: (token: string) => {
    localStorage.setItem('accessToken', token);
    set({ accessToken: token });
  },

  logout: () => {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    localStorage.removeItem('user');
    
    set({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
    });
  },

  initializeFromLocalStorage: () => {
    const accessToken = localStorage.getItem('accessToken');
    const refreshToken = localStorage.getItem('refreshToken');
    const userJson = localStorage.getItem('user');

    if (accessToken && userJson) {
      try {
        const user = JSON.parse(userJson);
        set({
          user,
          accessToken,
          refreshToken,
          isAuthenticated: true,
        });
      } catch (error) {
        console.error('Failed to parse stored user:', error);
      }
    }
  },
}));
