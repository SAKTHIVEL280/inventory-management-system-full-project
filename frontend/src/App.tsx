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
import CategoriesPage from './pages/CategoriesPage';
import ProductsPage from './pages/ProductsPage';
import PurchaseOrderPage from './pages/PurchaseOrderPage';
import QuotationsPage from './pages/QuotationsPage';
import SalesOrdersPage from './pages/SalesOrdersPage';
import InvoicesPage from './pages/InvoicesPage';
import GRNPage from './pages/GRNPage';
import StockPage from './pages/StockPage';
import ReceivablesPage from './pages/ReceivablesPage';
import PayablesPage from './pages/PayablesPage';
import ReportsPage from './pages/ReportsPage';
import { PERMISSION_SCOPES } from './types';
import { Toaster } from 'sonner';
import { authApi } from './api/auth';
import { ConfirmDialogHost } from './components/ConfirmDialogHost';

function App() {
  const { initializeFromLocalStorage, isAuthenticated, setUser, logout } = useAuthStore();
  const [isInitialized, setIsInitialized] = useState(false);

  useEffect(() => {
    // Initialize auth from localStorage on app startup
    initializeFromLocalStorage();
    setIsInitialized(true);
  }, [initializeFromLocalStorage]);

  useEffect(() => {
    if (!isInitialized || !isAuthenticated) {
      return;
    }

    // Always refresh effective permissions from backend so action buttons
    // don't disappear due to stale localStorage user payload.
    authApi
      .getMe()
      .then((user) => {
        setUser(user);
      })
      .catch(() => {
        logout();
      });
  }, [isInitialized, isAuthenticated, setUser, logout]);

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
    <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Toaster richColors position="top-right" closeButton />
      <ConfirmDialogHost />
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

        {/* ── Masters ─────────────────────────────────────── */}
        <Route
          path="/masters/company"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.COMPANY_READ}>
              <CompanyPage />
            </ProtectedRoute>
          }
        />
        <Route path="/company" element={<Navigate to="/masters/company" replace />} />

        <Route
          path="/masters/users"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.USERS_READ}>
              <UsersPage />
            </ProtectedRoute>
          }
        />
        <Route path="/users" element={<Navigate to="/masters/users" replace />} />

        <Route
          path="/masters/customers"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.CUSTOMERS_READ}>
              <CustomersPage />
            </ProtectedRoute>
          }
        />
        <Route path="/customers" element={<Navigate to="/masters/customers" replace />} />

        <Route
          path="/masters/suppliers"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.SUPPLIERS_READ}>
              <SuppliersPage />
            </ProtectedRoute>
          }
        />
        <Route path="/suppliers" element={<Navigate to="/masters/suppliers" replace />} />

        <Route
          path="/masters/categories"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.PRODUCTS_READ}>
              <CategoriesPage />
            </ProtectedRoute>
          }
        />
        <Route path="/categories" element={<Navigate to="/masters/categories" replace />} />

        <Route
          path="/masters/products"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.PRODUCTS_READ}>
              <ProductsPage />
            </ProtectedRoute>
          }
        />
        <Route path="/products" element={<Navigate to="/masters/products" replace />} />

        {/* ── Purchase ────────────────────────────────────── */}
        <Route
          path="/purchase/orders"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.PURCHASE_ORDERS_READ}>
              <PurchaseOrderPage />
            </ProtectedRoute>
          }
        />
        <Route path="/purchase-orders" element={<Navigate to="/purchase/orders" replace />} />

        <Route
          path="/purchase/grn"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.GRN_READ}>
              <GRNPage />
            </ProtectedRoute>
          }
        />
        <Route path="/grn" element={<Navigate to="/purchase/grn" replace />} />

        {/* ── Sales ───────────────────────────────────────── */}
        <Route
          path="/sales/quotations"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.QUOTATIONS_READ}>
              <QuotationsPage />
            </ProtectedRoute>
          }
        />
        <Route path="/quotations" element={<Navigate to="/sales/quotations" replace />} />

        <Route
          path="/sales/orders"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.SALES_ORDERS_READ}>
              <SalesOrdersPage />
            </ProtectedRoute>
          }
        />
        <Route path="/sales-orders" element={<Navigate to="/sales/orders" replace />} />

        <Route
          path="/sales/invoices"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.SALES_INVOICES_READ}>
              <InvoicesPage />
            </ProtectedRoute>
          }
        />
        <Route path="/invoices" element={<Navigate to="/sales/invoices" replace />} />

        {/* ── Inventory ───────────────────────────────────── */}
        <Route
          path="/inventory/stock"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.STOCK_LEDGER_READ}>
              <StockPage />
            </ProtectedRoute>
          }
        />
        <Route path="/stock" element={<Navigate to="/inventory/stock" replace />} />

        {/* ── Payments ────────────────────────────────────── */}
        <Route
          path="/payments/receivables"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.RECEIPTS_READ}>
              <ReceivablesPage />
            </ProtectedRoute>
          }
        />
        <Route path="/receivables" element={<Navigate to="/payments/receivables" replace />} />

        <Route
          path="/payments/payables"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.PAYMENTS_READ}>
              <PayablesPage />
            </ProtectedRoute>
          }
        />
        <Route path="/payables" element={<Navigate to="/payments/payables" replace />} />

        {/* ── Reports ─────────────────────────────────────── */}
        <Route
          path="/reports"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.REPORTS_READ}>
              <ReportsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/reports/:reportType"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.REPORTS_READ}>
              <ReportsPage />
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
