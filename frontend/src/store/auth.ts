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
  isAuthenticated: boolean;
  isLoading: boolean;

  // Actions
  setAuth: (token: AuthToken) => void;
  setUser: (user: User) => void;
  setAuthenticated: (isAuthenticated: boolean) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthStore>((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: false,

  setAuth: (token: AuthToken) => {
    set({
      user: token.user,
      isAuthenticated: true,
    });
  },

  setUser: (user: User) => {
    set({ user });
  },

  setAuthenticated: (isAuthenticated: boolean) => {
    set({ isAuthenticated });
  },

  logout: () => {
    set({
      user: null,
      isAuthenticated: false,
    });
  },
}));
