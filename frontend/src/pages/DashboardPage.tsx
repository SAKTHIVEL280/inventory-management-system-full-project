/**
 * Dashboard Page
 * 
 * Main page after login - shows user info and provides navigation.
 */

import { useAuthStore } from '../store/auth';
import { usePermissions } from '../hooks/usePermissions';
import { Link } from 'react-router-dom';
import { AppLayout } from '../components/AppLayout';
import {
  Building2,
  Users,
  Warehouse,
  ShoppingCart,
  BarChart3,
  ChevronRight,
} from 'lucide-react';

const roleClassMap: Record<string, string> = {
  admin: 'bg-role-admin',
  accounting: 'bg-role-accounting',
  sales: 'bg-role-sales',
  inventory: 'bg-role-inventory',
};

interface ModuleSection {
  title: string;
  description: string;
  icon: React.ReactNode;
  items: { label: string; to: string; permission?: string }[];
}

const DashboardPage = () => {
  const user = useAuthStore((state) => state.user);
  const { can } = usePermissions();

  const quickLinkClassName =
    'group flex items-center justify-between rounded-xl border border-neutral-200 bg-white px-4 py-3 text-sm font-semibold text-neutral-700 transition hover:border-primary/30 hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary';

  const roleColorClass = roleClassMap[user?.role ?? ''] ?? 'bg-primary';
  const permissionCount = user?.effective_access?.length || 0;

  const sections: ModuleSection[] = [
    {
      title: 'Administration',
      description: 'System and user management',
      icon: <Building2 size={20} aria-hidden="true" />,
      items: [
        { label: 'Company Settings', to: '/company', permission: 'company_read' },
        { label: 'User Management', to: '/users', permission: 'users_read' },
      ],
    },
    {
      title: 'Operations',
      description: 'Partners and inventory',
      icon: <Warehouse size={20} aria-hidden="true" />,
      items: [
        { label: 'Customers', to: '/customers', permission: 'customers_read' },
        { label: 'Suppliers', to: '/suppliers', permission: 'suppliers_read' },
        { label: 'Stock Ledger', to: '/products', permission: 'stock_ledger_read' },
      ],
    },
    {
      title: 'Sales & Procurement',
      description: 'Orders and transactions',
      icon: <ShoppingCart size={20} aria-hidden="true" />,
      items: [
        { label: 'Sales Orders', to: '/products', permission: 'sales_orders_read' },
        { label: 'Purchase Orders', to: '/products', permission: 'purchase_orders_read' },
      ],
    },
    {
      title: 'Reporting',
      description: 'Analytics and insights',
      icon: <BarChart3 size={20} aria-hidden="true" />,
      items: [
        { label: 'Reports', to: '/dashboard', permission: 'reports_read' },
      ],
    },
  ];

  const filteredSections = sections.map((section) => ({
    ...section,
    items: section.items.filter((item) => !item.permission || can(item.permission)),
  })).filter((section) => section.items.length > 0);

  return (
    <AppLayout title="Dashboard">
      <div className="space-y-8">
        {/* User Profile Card */}
        <section className="grid grid-cols-1 gap-6 md:grid-cols-3">
          <article className="hms-card p-6">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Signed in as</p>
                <p className="mt-3 text-lg font-bold text-neutral-900">{user?.full_name}</p>
                <p className="mt-1 text-sm text-neutral-500">{user?.email}</p>
              </div>
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
                <Users size={20} className="text-primary" aria-hidden="true" />
              </div>
            </div>
          </article>

          <article className="hms-card p-6">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Role & Access</p>
                <p className="mt-3 text-lg font-bold text-neutral-900">{user?.role}</p>
                <span className={`mt-2 inline-block rounded-full px-2.5 py-1 text-xs font-bold uppercase tracking-wide text-white ${roleColorClass}`}>
                  {user?.role}
                </span>
              </div>
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-success/10">
                <span className="material-icons text-success" aria-hidden="true">verified_user</span>
              </div>
            </div>
          </article>

          <article className="hms-card p-6">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Accessible modules</p>
                <p className="mt-3 text-2xl font-bold text-neutral-900">{permissionCount}</p>
                <p className="mt-1 text-xs text-neutral-500">Based on effective access</p>
              </div>
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
                <span className="material-icons text-primary" aria-hidden="true">apps</span>
              </div>
            </div>
          </article>
        </section>

        {/* Module Sections by Permission */}
        {filteredSections.map((section, idx) => (
          <section key={idx} className="hms-card overflow-hidden">
            <div className="border-b border-neutral-200 bg-gradient-to-r from-neutral-50 to-white px-6 py-5">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  {section.icon}
                </div>
                <div>
                  <h2 className="font-display text-lg font-bold text-neutral-900">{section.title}</h2>
                  <p className="text-xs text-neutral-500">{section.description}</p>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3 p-6 md:grid-cols-2 lg:grid-cols-3">
              {section.items.map((item) => (
                <Link
                  key={item.to}
                  to={item.to}
                  className={quickLinkClassName}
                >
                  <span className="flex items-center gap-2">
                    <span className="material-icons text-[18px] text-neutral-500" aria-hidden="true">
                      {section.title === 'Administration' && item.label.includes('Company') && 'corporate_fare'}
                      {section.title === 'Administration' && item.label.includes('User') && 'people'}
                      {section.title === 'Operations' && item.label.includes('Customer') && 'person_outline'}
                      {section.title === 'Operations' && item.label.includes('Supplier') && 'local_shipping'}
                      {section.title === 'Operations' && item.label.includes('Stock') && 'inventory_2'}
                      {section.title === 'Sales & Procurement' && item.label.includes('Sales') && 'shopping_cart'}
                      {section.title === 'Sales & Procurement' && item.label.includes('Purchase') && 'file_download'}
                      {section.title === 'Reporting' && item.label.includes('Reports') && 'bar_chart'}
                    </span>
                    <span>{item.label}</span>
                  </span>
                  <ChevronRight size={16} className="text-neutral-400 transition group-hover:translate-x-1 group-hover:text-primary" />
                </Link>
              ))}
            </div>
          </section>
        ))}

        {/* Footer Note */}
        <div className="hms-card p-6">
          <p className="text-sm text-neutral-600">
            <span className="font-semibold">Implementation in progress.</span> More features like real-time KPIs, recent activity, and detailed reports coming soon!
          </p>
        </div>
      </div>
    </AppLayout>
  );
};

export default DashboardPage;
