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

        <Route
          path="/purchase-orders"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.PURCHASE_ORDERS_READ}>
              <PurchaseOrderPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/quotations"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.QUOTATIONS_READ}>
              <QuotationsPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/sales-orders"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.SALES_ORDERS_READ}>
              <SalesOrdersPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/invoices"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.SALES_INVOICES_READ}>
              <InvoicesPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/grn"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.GRN_READ}>
              <GRNPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/stock"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.STOCK_LEDGER_READ}>
              <StockPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/receivables"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.RECEIPTS_READ}>
              <ReceivablesPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/payables"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.PAYMENTS_READ}>
              <PayablesPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/reports"
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
