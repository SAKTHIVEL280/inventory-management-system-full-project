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

const LoginPage = () => {
  const navigate = useNavigate();
  const setAuth = useAuthStore((state) => state.setAuth);
  
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showChangePassword, setShowChangePassword] = useState(false);
  const [changePasswordData, setChangePasswordData] = useState({
    current_password: '',
    new_password: '',
    confirm_password: '',
  });
  const [changePasswordError, setChangePasswordError] = useState('');

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
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
    } catch (err: any) {
      setError(
        err.response?.data?.detail ||
        'Invalid email or password'
      );
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
    } catch (err: any) {
      setChangePasswordError(
        err.response?.data?.detail ||
        'Failed to change password'
      );
    } finally {
      setIsLoading(false);
    }
  };

  if (showChangePassword) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background-light p-4">
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
              <input
                id="current_password"
                type="password"
                autoComplete="current-password"
                value={changePasswordData.current_password}
                onChange={(e) =>
                  setChangePasswordData({
                    ...changePasswordData,
                    current_password: e.target.value,
                  })
                }
                className="hms-input"
                required
              />
            </div>

            <div>
              <label htmlFor="new_password" className="hms-label">
                New Password (min 8 chars, 1 uppercase, 1 number)
              </label>
              <input
                id="new_password"
                type="password"
                autoComplete="new-password"
                value={changePasswordData.new_password}
                onChange={(e) =>
                  setChangePasswordData({
                    ...changePasswordData,
                    new_password: e.target.value,
                  })
                }
                className="hms-input"
                required
              />
            </div>

            <div>
              <label htmlFor="confirm_password" className="hms-label">
                Confirm Password
              </label>
              <input
                id="confirm_password"
                type="password"
                autoComplete="new-password"
                value={changePasswordData.confirm_password}
                onChange={(e) =>
                  setChangePasswordData({
                    ...changePasswordData,
                    confirm_password: e.target.value,
                  })
                }
                className="hms-input"
                required
              />
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
    <div className="flex min-h-screen items-center justify-center bg-background-light p-4">
      <div className="hms-card w-full max-w-xl p-8 sm:p-10">
        
        <h1 className="mt-4 font-display text-3xl font-bold leading-tight text-neutral-900">Inventory Management System</h1>
        <p className="mt-2 text-sm text-neutral-500">Use your assigned credentials to continue</p>

        <form onSubmit={handleLogin} className="mt-8 space-y-4">
          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700" role="alert" aria-live="assertive">
              {error}
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
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="hms-input"
              placeholder="••••••••"
              required
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-bold text-white shadow-lg shadow-primary/20 transition hover:bg-primary/90 disabled:opacity-50"
          >
            {isLoading ? 'Logging in...' : 'Login'}
          </button>
        </form>

        <p className="mt-4 text-center text-xs font-medium text-neutral-500">
          Demo credentials: admin@company.com / Admin@123
        </p>
      </div>
    </div>
  );
};

export default LoginPage;
