/**
 * Main App Component
 * 
 * Handles routing, auth initialization, and token refresh.
 */

import { useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useAuthStore } from './store/auth';
import { ProtectedRoute } from './routes/ProtectedRoute';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import CompanyPage from './pages/CompanyPage';
import UsersPage from './pages/UsersPage';
import CustomersPage from './pages/CustomersPage';
import SuppliersPage from './pages/SuppliersPage';
import ProductsPage from './pages/ProductsPage';
import { PERMISSION_SCOPES } from './types';

function App() {
  const { initializeFromLocalStorage, isAuthenticated } = useAuthStore();
  const [isInitialized, setIsInitialized] = useState(false);

  useEffect(() => {
    // Initialize auth from localStorage on app startup
    initializeFromLocalStorage();
    setIsInitialized(true);
  }, [initializeFromLocalStorage]);

  if (!isInitialized) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50" role="status" aria-live="polite">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <Router>
      <Routes>
        {/* Public routes */}
        <Route
          path="/login"
          element={
            isAuthenticated ? <Navigate to="/dashboard" replace /> : <LoginPage />
          }
        />

        {/* Protected routes */}
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <DashboardPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/company"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.COMPANY_READ}>
              <CompanyPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/users"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.USERS_READ}>
              <UsersPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/customers"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.CUSTOMERS_READ}>
              <CustomersPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/suppliers"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.SUPPLIERS_READ}>
              <SuppliersPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/products"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.PRODUCTS_READ}>
              <ProductsPage />
            </ProtectedRoute>
          }
        />

        {/* Catch all - redirect to dashboard or login */}
        <Route
          path="/"
          element={
            <Navigate to={isAuthenticated ? '/dashboard' : '/login'} replace />
          }
        />

        <Route
          path="*"
          element={<Navigate to={isAuthenticated ? '/dashboard' : '/login'} replace />}
        />
      </Routes>
    </Router>
  );
}

export default App;
