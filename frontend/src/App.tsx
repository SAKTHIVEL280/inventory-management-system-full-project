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
import CustomizationOptionsPage from './pages/CustomizationOptionsPage';
import PurchaseOrderPage from './pages/PurchaseOrderPage';
import QuotationsPage from './pages/QuotationsPage';
import InvoicesPage from './pages/InvoicesPage';
import RDNPage from './pages/RDNPage';
import RDNCreditNotePage from './pages/RDNCreditNotePage';
import GRNPage from './pages/GRNPage';
import StockPage from './pages/StockPage';
import InventoryCountPage from './pages/InventoryCountPage';
import InventoryCountDifferencePage from './pages/InventoryCountDifferencePage';
import ReceivablesPage from './pages/ReceivablesPage';
import PayablesPage from './pages/PayablesPage';
import ReportsPage from './pages/ReportsPage';
import ActionLogsPage from './pages/ActionLogsPage';
import { PERMISSION_SCOPES } from './types';
import { Toaster } from 'sonner';
import { authApi } from './api/auth';
import { ConfirmDialogHost } from './components/ConfirmDialogHost';

const withTimeout = <T,>(promise: Promise<T>, timeoutMs = 15000): Promise<T> => {
  return new Promise<T>((resolve, reject) => {
    const timeoutId = window.setTimeout(() => {
      reject(new Error(`Request timed out after ${timeoutMs}ms`));
    }, timeoutMs);

    promise
      .then((value) => {
        window.clearTimeout(timeoutId);
        resolve(value);
      })
      .catch((error) => {
        window.clearTimeout(timeoutId);
        reject(error);
      });
  });
};

function App() {
  const { isAuthenticated, setUser, setAuthenticated, logout } = useAuthStore();
  const [isInitialized, setIsInitialized] = useState(false);

  useEffect(() => {
    let active = true;

    const bootstrapSession = async () => {
      try {
        const user = await withTimeout(authApi.getMe(), 12000);
        if (!active) {
          return;
        }
        setUser(user);
        setAuthenticated(true);
      } catch {
        if (!active) {
          return;
        }
        logout();
      } finally {
        if (active) {
          setIsInitialized(true);
        }
      }
    };

    void bootstrapSession();

    return () => {
      active = false;
    };
  }, [logout, setAuthenticated, setUser]);

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
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.COMPANY_WRITE}>
              <CompanyPage />
            </ProtectedRoute>
          }
        />
        <Route path="/company" element={<Navigate to="/masters/company" replace />} />

        <Route
          path="/masters/users"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.USERS_WRITE}>
              <UsersPage />
            </ProtectedRoute>
          }
        />
        <Route path="/users" element={<Navigate to="/masters/users" replace />} />

        <Route
          path="/masters/customers"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.CUSTOMERS_WRITE}>
              <CustomersPage />
            </ProtectedRoute>
          }
        />
        <Route path="/customers" element={<Navigate to="/masters/customers" replace />} />

        <Route
          path="/masters/suppliers"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.SUPPLIERS_WRITE}>
              <SuppliersPage />
            </ProtectedRoute>
          }
        />
        <Route path="/suppliers" element={<Navigate to="/masters/suppliers" replace />} />

        <Route
          path="/masters/categories"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.CATEGORIES_WRITE}>
              <CategoriesPage />
            </ProtectedRoute>
          }
        />
        <Route path="/categories" element={<Navigate to="/masters/categories" replace />} />

        <Route
          path="/masters/products"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.PRODUCTS_WRITE}>
              <ProductsPage />
            </ProtectedRoute>
          }
        />
        <Route path="/products" element={<Navigate to="/masters/products" replace />} />

        <Route
          path="/masters/customization-options"
          element={
            <ProtectedRoute requiredRole="admin">
              <CustomizationOptionsPage />
            </ProtectedRoute>
          }
        />

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
          path="/sales/invoices"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.SALES_INVOICES_READ}>
              <InvoicesPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/sales/rdn"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.RDN_READ}>
              <RDNPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/sales/rdn-credit-notes"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.RDN_READ}>
              <RDNCreditNotePage />
            </ProtectedRoute>
          }
        />
        <Route path="/sales/orders" element={<Navigate to="/sales/invoices" replace />} />
        <Route path="/sales-orders" element={<Navigate to="/sales/invoices" replace />} />
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
        <Route
          path="/inventory/count"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.STOCK_LEDGER_WRITE}>
              <InventoryCountPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/inventory/count-difference"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.STOCK_LEDGER_READ}>
              <InventoryCountDifferencePage />
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

        {/* ── Action Logs ─────────────────────────────────── */}
        <Route
          path="/reports/action-logs"
          element={
            <ProtectedRoute requiredPermission={PERMISSION_SCOPES.ACTION_LOGS_READ}>
              <ActionLogsPage />
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
