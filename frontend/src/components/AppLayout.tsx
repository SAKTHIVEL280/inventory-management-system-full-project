import { ReactNode, useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useAuthStore } from '../store/auth';
import { usePermissions } from '../hooks/usePermissions';
import { companyApi } from '../api/company';
import { getStaticUrl } from '../utils/url_utils';
import { archiveApi } from '../api/archive';
import { toast } from 'sonner';

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

interface NavGroup {
  key: string;
  label: string;
  icon: string;
  items: NavItem[];
}

export const AppLayout = ({ title, children }: AppLayoutProps) => {
  const location = useLocation();
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const logoutFromStore = useAuthStore((state) => state.logout);
  const { can } = usePermissions();
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
  const [showArchivePurgeModal, setShowArchivePurgeModal] = useState(false);
  const [confirmationText, setConfirmationText] = useState('');

  const { data: company } = useQuery({
    queryKey: ['company-branding'],
    queryFn: companyApi.getBranding,
    staleTime: 5 * 60 * 1000,
    enabled: Boolean(user),
  });

  const { data: archiveAlerts } = useQuery({
    queryKey: ['archive-login-alerts'],
    queryFn: async () => {
      try {
        const response = await archiveApi.getLoginAlerts();
        return response.data;
      } catch (error: unknown) {
        const status = (error as { response?: { status?: number } })?.response?.status;
        if (status === 404) {
          return {
            requires_attention: false,
            modules: [],
            actionable_modules: [],
            protected_modules: [],
            message: '',
            default_action: 'extend_retention',
            policy: {
              no_auto_hard_delete_for: [],
              review_window_days: 7,
            },
          };
        }
        throw error;
      }
    },
    staleTime: 60 * 1000,
    enabled: Boolean(user),
    retry: false,
  });

  const {
    mutate: openPurgePreview,
    data: purgePreview,
    isPending: previewLoading,
  } = useMutation({
    mutationFn: () => archiveApi.getPurgePreview().then((r) => r.data),
    onSuccess: () => {
      setConfirmationText('');
      setShowArchivePurgeModal(true);
    },
  });

  const { mutate: confirmPurge, isPending: confirmLoading } = useMutation({
    mutationFn: (text: string) => archiveApi.confirmPurge(text).then((r) => r.data),
    onSuccess: (result) => {
      toast.success(`Archive purge complete. Deleted ${result.deleted}, skipped ${result.skipped}.`);
      setShowArchivePurgeModal(false);
      setConfirmationText('');
    },
  });

  const isAdmin = ['admin', 'doctor', 'accounts'].includes(user?.role?.toLowerCase() ?? '');

  const navGroups: NavGroup[] = useMemo(() => [
    {
      key: 'dashboard',
      label: 'Dashboard',
      icon: 'dashboard',
      items: [{ to: '/dashboard', label: 'Dashboard', visible: true, icon: 'dashboard' }],
    },
    {
      key: 'masters',
      label: 'Masters',
      icon: 'folder',
      items: [
        { to: '/masters/company', label: 'Company', visible: can('company_read'), icon: 'corporate_fare' },
        { to: '/masters/users', label: 'Users', visible: can('users_read'), icon: 'groups' },
        { to: '/masters/customers', label: 'Customers', visible: can('customers_read'), icon: 'person' },
        { to: '/masters/suppliers', label: 'Suppliers', visible: can('suppliers_read'), icon: 'local_shipping' },
        { to: '/masters/categories', label: 'Categories', visible: can('products_read'), icon: 'label' },
        { to: '/masters/products', label: 'Products', visible: can('products_read'), icon: 'inventory_2' },
      ],
    },
    {
      key: 'inventory',
      label: 'Inventory',
      icon: 'warehouse',
      items: [
        { to: '/inventory/stock', label: 'Stock', visible: can('stock_ledger_read'), icon: 'warehouse' },
        { to: '/inventory/count', label: 'Inventory Count', visible: can('stock_ledger_write'), icon: 'fact_check' },
        { to: '/inventory/count-difference', label: 'Count Difference', visible: can('stock_ledger_read'), icon: 'difference' },
      ],
    },
    {
      key: 'purchase',
      label: 'Purchase',
      icon: 'shopping_cart',
      items: [
        { to: '/purchase/orders', label: 'Purchase Orders', visible: can('purchase_orders_read'), icon: 'shopping_cart' },
        { to: '/purchase/grn', label: 'Good Receipt Notes', visible: can('grn_read'), icon: 'move_to_inbox' },
      ],
    },
    {
      key: 'sales',
      label: 'Sales',
      icon: 'receipt_long',
      items: [
        { to: '/sales/quotations', label: 'Quotations', visible: can('quotations_read'), icon: 'request_quote' },
        { to: '/sales/invoices', label: 'Sales Invoice', visible: can('sales_invoices_read'), icon: 'receipt' },
      ],
    },
    {
      key: 'accounts',
      label: 'Accounts',
      icon: 'account_balance_wallet',
      items: [
        { to: '/payments/receivables', label: 'Receivables', visible: can('receipts_read'), icon: 'account_balance_wallet' },
        { to: '/payments/payables', label: 'Payables', visible: can('payments_read'), icon: 'payments' },
      ],
    },
    {
      key: 'reports',
      label: 'Reports',
      icon: 'bar_chart',
      items: [{ to: '/reports', label: 'Reports', visible: can('reports_read'), icon: 'bar_chart' }],
    },
  ], [can, isAdmin]);

  const getGroupForPath = useCallback((pathname: string): string => {
    for (const group of navGroups) {
      if (group.items.some((item) => item.visible && item.to === pathname)) {
        return group.key;
      }
    }

    const firstVisible = navGroups.find((group) => group.items.some((item) => item.visible));
    return firstVisible?.key ?? 'dashboard';
  }, [navGroups]);

  const getVisibleItems = (group: NavGroup): NavItem[] => group.items.filter((item) => item.visible);

  const [openGroup, setOpenGroup] = useState<string>(() => getGroupForPath(location.pathname));

  useEffect(() => {
    const activeGroup = getGroupForPath(location.pathname);
    setOpenGroup((prev) => (prev === activeGroup ? prev : activeGroup));
  }, [location.pathname, getGroupForPath]);

  const mobileNavItems = navGroups.flatMap((group) => group.items).filter((item) => item.visible);

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
    <div className="min-h-screen bg-neutral-50">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2"
      >
        Skip to main content
      </a>

      <div className="min-h-screen">
        <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-neutral-200 bg-white lg:block overflow-hidden">
          <div className="flex h-full flex-col p-6">
            <div className="mb-8 flex items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary">
                {company?.logo_data_url || company?.logo_url ? (
                  <img src={company.logo_data_url || getStaticUrl(company.logo_url) || ''} alt={company.name} className="h-full w-full rounded-full object-cover" />
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

            <nav aria-label="Primary" className="flex-1 space-y-1 overflow-hidden">
              {navGroups
                .filter((group) => group.items.some((item) => item.visible))
                .map((group) => {
                  const visibleItems = getVisibleItems(group);
                  const hasDropdown = visibleItems.length > 1;
                  const isExpanded = openGroup === group.key;
                  const isGroupActive = visibleItems.some((item) => location.pathname === item.to);

                  if (!hasDropdown) {
                    const item = visibleItems[0];
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
                  }

                  return (
                    <div key={group.key} className="pt-1 first:pt-0">
                      <button
                        type="button"
                        onClick={() => setOpenGroup((prev) => (prev === group.key ? '' : group.key))}
                        className={`flex w-full items-center justify-between gap-2 rounded-lg px-4 py-2 text-left text-xs font-bold uppercase tracking-wider transition-colors ${
                          isGroupActive && !isExpanded
                            ? 'bg-primary/10 text-primary'
                            : 'text-neutral-500 hover:bg-neutral-50'
                        }`}
                      >
                        <span className="flex items-center gap-2">
                          <span className="material-icons text-[16px]" aria-hidden="true">{group.icon}</span>
                          <span>{group.label}</span>
                        </span>
                        <span className="material-icons text-[18px]" aria-hidden="true">
                          {isExpanded ? 'expand_less' : 'expand_more'}
                        </span>
                      </button>

                      {isExpanded && (
                        <div className="ml-4 space-y-1 border-l border-neutral-200 pl-3">
                          {visibleItems.map((item) => {
                            const isActive = location.pathname === item.to;

                            return (
                              <Link
                                key={item.to}
                                to={item.to}
                                className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-semibold transition-colors ${
                                  isActive
                                    ? 'bg-primary/10 text-primary'
                                    : 'text-neutral-600 hover:bg-neutral-50 hover:text-primary'
                                }`}
                              >
                                <span className="material-icons text-[18px]" aria-hidden="true">{item.icon}</span>
                                <span>{item.label}</span>
                              </Link>
                            );
                          })}
                        </div>
                      )}
                    </div>
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

        <div className="min-h-screen lg:ml-64">
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
            {archiveAlerts?.requires_attention && (
              <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
                <div className="flex items-start gap-3">
                  <span className="material-icons text-amber-600" aria-hidden="true">warning_amber</span>
                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-amber-900">Archive retention review required</p>
                    <p className="text-xs text-amber-800">{archiveAlerts.message} Protected modules (Invoices, Payments, Stock Ledger) are not auto hard-deleted.</p>
                    <p className="text-xs text-amber-800">
                      Due soon/overdue:
                      {' '}
                      {archiveAlerts.modules
                        .filter((m) => m.due_soon > 0 || m.overdue > 0)
                        .map((m) => `${m.label} (${m.due_soon} soon, ${m.overdue} overdue)`)
                        .join(' | ')}
                    </p>
                    {isAdmin && (
                      <div className="pt-1">
                        <button
                          type="button"
                          onClick={() => openPurgePreview()}
                          disabled={previewLoading}
                          className="rounded-lg border border-amber-300 bg-amber-100 px-3 py-1.5 text-xs font-semibold text-amber-900 transition hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {previewLoading ? 'Loading purge preview...' : 'Review purge candidates'}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </header>

          <div className="mx-auto w-full max-w-[1536px] px-4 py-6 sm:px-6 lg:px-8">
            <nav aria-label="Mobile primary" className="mb-6 flex flex-wrap gap-2 lg:hidden">
              {mobileNavItems.map((item) => (
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

      {showArchivePurgeModal && purgePreview && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
          <div className="hms-card w-full max-w-2xl space-y-6 p-6">
            <div>
              <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-amber-100">
                <span className="material-icons text-amber-700" aria-hidden="true">gpp_maybe</span>
              </div>
              <h2 className="font-display text-lg font-bold text-neutral-900">Archive Purge Confirmation</h2>
              <p className="mt-2 text-sm text-neutral-600">{purgePreview.warning}</p>
              <p className="mt-1 text-sm font-semibold text-neutral-800">
                Overdue purge candidates: {purgePreview.purge_candidates}
              </p>
              <p className="mt-2 text-xs text-neutral-600">
                Type this exact confirmation text to continue: <span className="font-semibold text-neutral-900">{purgePreview.expected_confirmation_text}</span>
              </p>
            </div>

            <div className="rounded-lg border border-neutral-200 bg-neutral-50 p-3">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">Modules overview</p>
              <div className="max-h-44 space-y-1 overflow-auto text-xs text-neutral-700">
                {purgePreview.modules.map((m) => (
                  <p key={m.key}>
                    {m.label}: archived {m.total_archived}, due soon {m.due_soon}, overdue {m.overdue}
                    {!m.purge_allowed ? ' (protected)' : ''}
                  </p>
                ))}
              </div>
            </div>

            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-neutral-600" htmlFor="archive-confirm-text">
                Confirmation Text
              </label>
              <input
                id="archive-confirm-text"
                value={confirmationText}
                onChange={(e) => setConfirmationText(e.target.value)}
                className="hms-input"
                placeholder={purgePreview.expected_confirmation_text}
              />
            </div>

            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => {
                  setShowArchivePurgeModal(false);
                  setConfirmationText('');
                }}
                className="flex-1 rounded-lg border border-neutral-200 bg-white px-4 py-2.5 text-sm font-semibold text-neutral-600 transition hover:bg-neutral-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => confirmPurge(confirmationText)}
                disabled={confirmLoading || confirmationText !== purgePreview.expected_confirmation_text}
                className="flex-1 rounded-lg bg-amber-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-amber-600/20 transition hover:bg-amber-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {confirmLoading ? 'Purging...' : 'Confirm Manual Purge'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
