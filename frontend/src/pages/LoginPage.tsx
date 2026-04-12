/**
 * Login Page
 * 
 * User authentication form with email/password login.
 * Handles password change modal on first login (force_password_change=true).
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/auth';
import { authApi } from '../api/auth';
import { LoginRequest } from '../types';
import type { AxiosError } from 'axios';

const LoginPage = () => {
  const navigate = useNavigate();
  const setAuth = useAuthStore((state) => state.setAuth);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isLocked, setIsLocked] = useState(false);
  const [showChangePassword, setShowChangePassword] = useState(false);
  const [showLoginPassword, setShowLoginPassword] = useState(false);
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [changePasswordData, setChangePasswordData] = useState({
    current_password: '',
    new_password: '',
    confirm_password: '',
  });
  const [changePasswordError, setChangePasswordError] = useState('');

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLocked(false);
    setIsLoading(true);

    try {
      const credentials: LoginRequest = { email, password };
      const token = await authApi.login(credentials);

      setAuth(token);

      if (token.user.force_password_change) {
        setShowChangePassword(true);
      } else {
        navigate('/dashboard');
      }
    } catch (err: unknown) {
      const axiosErr = err as AxiosError<{ detail?: string }>;
      if (axiosErr.response?.status === 423) {
        setIsLocked(true);
        setError(axiosErr.response.data?.detail || 'Account locked. Try again later.');
      } else {
        setError(axiosErr.response?.data?.detail || 'Invalid email or password');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setChangePasswordError('');
    setIsLoading(true);

    try {
      await authApi.changePassword(changePasswordData);
      navigate('/dashboard');
    } catch (err: unknown) {
      const axiosErr = err as AxiosError<{ detail?: string }>;
      setChangePasswordError(
        axiosErr.response?.data?.detail ||
        'Failed to change password'
      );
    } finally {
      setIsLoading(false);
    }
  };

  if (showChangePassword) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-neutral-50 p-4">
        <div className="hms-card w-full max-w-md p-8">
          <h1 className="font-display text-2xl font-bold text-neutral-900">Change Password</h1>
          <p className="mb-6 text-sm text-neutral-500">
            This is your first login. Please set a new password.
          </p>

          <form onSubmit={handleChangePassword} className="space-y-4">
            {changePasswordError && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700" role="alert" aria-live="assertive">
                {changePasswordError}
              </div>
            )}

            <div>
              <label htmlFor="current_password" className="hms-label">
                Current Password
              </label>
              <div className="relative">
                <input
                  id="current_password"
                  type={showCurrentPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  value={changePasswordData.current_password}
                  onChange={(e) =>
                    setChangePasswordData({
                      ...changePasswordData,
                      current_password: e.target.value,
                    })
                  }
                  className="hms-input pr-10"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowCurrentPassword((prev) => !prev)}
                  className="absolute inset-y-0 right-0 flex items-center px-3 text-neutral-500 hover:text-neutral-700"
                  aria-label={showCurrentPassword ? 'Hide current password' : 'Show current password'}
                >
                  <span className="material-icons text-base" aria-hidden="true">
                    {showCurrentPassword ? 'visibility_off' : 'visibility'}
                  </span>
                </button>
              </div>
            </div>

            <div>
              <label htmlFor="new_password" className="hms-label">
                New Password (min 8 chars, 1 uppercase, 1 number)
              </label>
              <div className="relative">
                <input
                  id="new_password"
                  type={showNewPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  value={changePasswordData.new_password}
                  onChange={(e) =>
                    setChangePasswordData({
                      ...changePasswordData,
                      new_password: e.target.value,
                    })
                  }
                  className="hms-input pr-10"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowNewPassword((prev) => !prev)}
                  className="absolute inset-y-0 right-0 flex items-center px-3 text-neutral-500 hover:text-neutral-700"
                  aria-label={showNewPassword ? 'Hide new password' : 'Show new password'}
                >
                  <span className="material-icons text-base" aria-hidden="true">
                    {showNewPassword ? 'visibility_off' : 'visibility'}
                  </span>
                </button>
              </div>
            </div>

            <div>
              <label htmlFor="confirm_password" className="hms-label">
                Confirm Password
              </label>
              <div className="relative">
                <input
                  id="confirm_password"
                  type={showConfirmPassword ? 'text' : 'password'}
                  autoComplete="new-password"
                  value={changePasswordData.confirm_password}
                  onChange={(e) =>
                    setChangePasswordData({
                      ...changePasswordData,
                      confirm_password: e.target.value,
                    })
                  }
                  className="hms-input pr-10"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword((prev) => !prev)}
                  className="absolute inset-y-0 right-0 flex items-center px-3 text-neutral-500 hover:text-neutral-700"
                  aria-label={showConfirmPassword ? 'Hide confirm password' : 'Show confirm password'}
                >
                  <span className="material-icons text-base" aria-hidden="true">
                    {showConfirmPassword ? 'visibility_off' : 'visibility'}
                  </span>
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-bold text-white shadow-lg shadow-primary/20 transition hover:bg-primary/90 disabled:opacity-50"
            >
              {isLoading ? 'Changing...' : 'Change Password'}
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-neutral-50 p-4">
      <div className="hms-card w-full max-w-xl p-8 sm:p-10">

        <h1 className="mt-4 font-display text-3xl font-bold leading-tight text-neutral-900"> Mecandria ERP</h1>
        <p className="mt-2 text-sm text-neutral-500">Use your assigned credentials to continue</p>

        <form onSubmit={handleLogin} className="mt-8 space-y-4">
          {error && (
            <div className={`rounded-lg border px-4 py-3 text-sm font-medium ${isLocked ? 'border-amber-200 bg-amber-50 text-amber-800' : 'border-red-200 bg-red-50 text-red-700'}`} role="alert" aria-live="assertive">
              <div className="flex items-start gap-2">
                <span className="material-icons text-base">{isLocked ? 'lock' : 'error_outline'}</span>
                <span>{error}</span>
              </div>
            </div>
          )}

          <div>
            <label htmlFor="email" className="hms-label">
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="hms-input"
              placeholder="admin@company.com"
              required
            />
          </div>

          <div>
            <label htmlFor="password" className="hms-label">
              Password
            </label>
            <div className="relative">
              <input
                id="password"
                type={showLoginPassword ? 'text' : 'password'}
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="hms-input pr-10"
                placeholder="••••••••"
                required
              />
              <button
                type="button"
                onClick={() => setShowLoginPassword((prev) => !prev)}
                className="absolute inset-y-0 right-0 flex items-center px-3 text-neutral-500 hover:text-neutral-700"
                aria-label={showLoginPassword ? 'Hide password' : 'Show password'}
              >
                <span className="material-icons text-base" aria-hidden="true">
                  {showLoginPassword ? 'visibility_off' : 'visibility'}
                </span>
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-bold text-white shadow-lg shadow-primary/20 transition hover:bg-primary/90 disabled:opacity-50"
          >
            {isLoading ? 'Logging in...' : 'Login'}
          </button>
        </form>

      </div>
    </div>
  );
};

export default LoginPage;
