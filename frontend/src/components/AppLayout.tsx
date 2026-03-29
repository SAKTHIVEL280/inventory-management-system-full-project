import { ReactNode, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuthStore } from '../store/auth';
import { usePermissions } from '../hooks/usePermissions';
import { companyApi } from '../api/company';

interface AppLayoutProps {
  title: string;
  children: ReactNode;
}

interface NavItem {
  to: string;
  label: string;
  visible: boolean;
  icon: string;
}

export const AppLayout = ({ title, children }: AppLayoutProps) => {
  const location = useLocation();
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const logoutFromStore = useAuthStore((state) => state.logout);
  const { can } = usePermissions();
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);

  const { data: company } = useQuery({
    queryKey: ['company'],
    queryFn: companyApi.get,
    staleTime: 5 * 60 * 1000,
  });

  const navItems: NavItem[] = [
    { to: '/dashboard', label: 'Dashboard', visible: true, icon: 'dashboard' },
    { to: '/masters/company', label: 'Company', visible: can('company_read'), icon: 'corporate_fare' },
    { to: '/masters/users', label: 'Users', visible: can('users_read'), icon: 'groups' },
    { to: '/masters/customers', label: 'Customers', visible: can('customers_read'), icon: 'person' },
    { to: '/masters/suppliers', label: 'Suppliers', visible: can('suppliers_read'), icon: 'local_shipping' },
    { to: '/masters/products', label: 'Products', visible: can('products_read'), icon: 'inventory_2' },
    { to: '/inventory/stock', label: 'Stock', visible: can('stock_ledger_read'), icon: 'warehouse' },
    { to: '/purchase/orders', label: 'Purchase Orders', visible: can('purchase_orders_read'), icon: 'shopping_cart' },
    { to: '/purchase/grn', label: 'GRN', visible: can('grn_read'), icon: 'move_to_inbox' },
    { to: '/sales/quotations', label: 'Quotations', visible: can('quotations_read'), icon: 'request_quote' },
    { to: '/sales/orders', label: 'Sales Orders', visible: can('sales_orders_read'), icon: 'receipt_long' },
    { to: '/sales/invoices', label: 'Invoices', visible: can('sales_invoices_read'), icon: 'receipt' },
    { to: '/payments/receivables', label: 'Receivables', visible: can('receipts_read'), icon: 'account_balance_wallet' },
    { to: '/payments/payables', label: 'Payables', visible: can('payments_read'), icon: 'payments' },
    { to: '/reports', label: 'Reports', visible: can('reports_read'), icon: 'bar_chart' },
  ];

  const handleLogoutClick = (): void => {
    setShowLogoutConfirm(true);
  };

  const handleConfirmLogout = (): void => {
    setShowLogoutConfirm(false);
    logoutFromStore();
    navigate('/login');
  };

  const handleCancelLogout = (): void => {
    setShowLogoutConfirm(false);
  };

  return (
    <div className="min-h-screen bg-background-light">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2"
      >
        Skip to main content
      </a>

      <div className="flex min-h-screen">
        <aside className="hidden w-64 shrink-0 border-r border-neutral-200 bg-white lg:block">
          <div className="p-6">
            <div className="mb-8 flex items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary">
                {company?.logo_url ? (
                  <img src={company.logo_url} alt={company.name} className="h-full w-full rounded-lg object-cover" />
                ) : (
                  <span className="material-icons text-white" aria-hidden="true">business</span>
                )}
              </div>
              <div className="flex-1 overflow-hidden">
                <p className="truncate text-sm font-semibold text-primary" title={company?.name || 'Inventory Management'}>
                  {company?.name || 'Inventory Management'}
                </p>
              </div>
            </div>

            <nav aria-label="Primary" className="space-y-1">
              {navItems.filter((item) => item.visible).map((item) => {
                const isActive = location.pathname === item.to;

                return (
                  <Link
                    key={item.to}
                    to={item.to}
                    className={`flex items-center gap-3 rounded-lg px-4 py-3 text-sm font-semibold transition-colors ${
                      isActive
                        ? 'bg-primary/10 text-primary'
                        : 'text-neutral-600 hover:bg-neutral-50 hover:text-primary'
                    }`}
                  >
                    <span className="material-icons text-[20px]" aria-hidden="true">{item.icon}</span>
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </nav>

            <div className="mt-auto border-t border-neutral-200 pt-6">
              <button
                type="button"
                onClick={handleLogoutClick}
                className="flex w-full items-center gap-3 rounded-lg px-4 py-3 text-sm font-semibold text-neutral-600 transition hover:bg-red-50 hover:text-red-600"
              >
                <span className="material-icons text-[20px]" aria-hidden="true">logout</span>
                <span>Logout</span>
              </button>
            </div>
          </div>
        </aside>

        <div className="flex-1">
          <header className="border-b border-neutral-200 bg-white px-6 py-4">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="font-display text-2xl font-bold text-neutral-900">{title}</h1>
              </div>
              <div className="flex items-center gap-3">
                <div className="text-right">
                  <p className="text-sm font-semibold text-neutral-900">{user?.full_name}</p>
                  <p className="text-xs uppercase tracking-wide text-neutral-500">{user?.role}</p>
                </div>
                <button
                  type="button"
                  onClick={handleLogoutClick}
                  className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm font-semibold text-neutral-600 transition hover:bg-neutral-50"
                >
                  Logout
                </button>
              </div>
            </div>
          </header>

          <div className="mx-auto w-full max-w-[1536px] px-4 py-6 sm:px-6 lg:px-8">
            <nav aria-label="Mobile primary" className="mb-6 flex flex-wrap gap-2 lg:hidden">
              {navItems.filter((item) => item.visible).map((item) => (
                <Link
                  key={item.to}
                  to={item.to}
                  className={`rounded-lg border px-3 py-2 text-sm font-medium ${
                    location.pathname === item.to
                      ? 'border-primary bg-primary text-white'
                      : 'border-neutral-200 bg-white text-neutral-600'
                  }`}
                >
                  {item.label}
                </Link>
              ))}
            </nav>

            <main id="main-content" tabIndex={-1}>{children}</main>
          </div>
        </div>
      </div>

      {/* Logout Confirmation Modal */}
      {showLogoutConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
          <div className="hms-card w-full max-w-sm space-y-6 p-6">
            <div>
              <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-red-100">
                <span className="material-icons text-red-600" aria-hidden="true">logout</span>
              </div>
              <h2 className="font-display text-lg font-bold text-neutral-900">Confirm Logout</h2>
              <p className="mt-2 text-sm text-neutral-600">
                Are you sure you want to logout? You will be redirected to the login page.
              </p>
            </div>

            <div className="flex gap-3">
              <button
                type="button"
                onClick={handleCancelLogout}
                className="flex-1 rounded-lg border border-neutral-200 bg-white px-4 py-2.5 text-sm font-semibold text-neutral-600 transition hover:bg-neutral-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmLogout}
                className="flex-1 rounded-lg bg-red-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-red-600/20 transition hover:bg-red-700"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
