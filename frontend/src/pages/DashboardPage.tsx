/**
 * Dashboard Page
 *
 * Main page after login - shows KPIs, charts, and navigation.
 */

import { usePermissions } from '../hooks/usePermissions';
import { Link } from 'react-router-dom';
import { AppLayout } from '../components/AppLayout';
import {
  Building2,
  Warehouse,
  ShoppingCart,
  BarChart3,
  ChevronRight,
  Settings,
  Users as UsersIcon,
  User,
  Truck,
  Package,
  Download,
  AlertTriangle,
  CreditCard,
  FileText,
  TrendingUp,
  IndianRupee,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { getDashboardStats, type DashboardStats as APIDashboardStats } from '../api/reports';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

interface ModuleSection {
  title: string;
  description: string;
  icon: React.ReactNode;
  items: { label: string; to: string; permission?: string; icon: React.ReactNode }[];
}

const DashboardPage = () => {
  const { can } = usePermissions();
  const [stats, setStats] = useState<APIDashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        setLoading(true);
        const data: APIDashboardStats = await getDashboardStats();
        setStats(data);
      } catch (error) {
        console.error('Failed to fetch dashboard stats:', error);
        setStats(null);
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
  }, []);

  const formatAmount = (paise: number) => `₹${(paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
  const formatAmountShort = (paise: number) => {
    const val = paise / 100;
    if (val >= 100000) return `₹${(val / 100000).toFixed(1)}L`;
    if (val >= 1000) return `₹${(val / 1000).toFixed(1)}K`;
    return `₹${val.toFixed(0)}`;
  };

  const quickLinkClassName =
    'group flex items-center justify-between rounded-xl border border-neutral-200 bg-white px-4 py-3 text-sm font-semibold text-neutral-700 transition hover:border-primary/30 hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary';

  const sections: ModuleSection[] = [
    {
      title: 'Administration',
      description: 'System and user management',
      icon: <Building2 size={20} aria-hidden="true" />,
      items: [
        { label: 'Company Settings', to: '/company', permission: 'company_read', icon: <Settings size={18} /> },
        { label: 'User Management', to: '/users', permission: 'users_read', icon: <UsersIcon size={18} /> },
      ],
    },
    {
      title: 'Master Data',
      description: 'Partners and inventory',
      icon: <Warehouse size={20} aria-hidden="true" />,
      items: [
        { label: 'Customers', to: '/customers', permission: 'customers_read', icon: <User size={18} /> },
        { label: 'Suppliers', to: '/suppliers', permission: 'suppliers_read', icon: <Truck size={18} /> },
        { label: 'Products', to: '/products', permission: 'products_read', icon: <Package size={18} /> },
        { label: 'Stock / Inventory', to: '/stock', permission: 'stock_ledger_read', icon: <Warehouse size={18} /> },
      ],
    },
    {
      title: 'Purchase',
      description: 'Procurement workflow',
      icon: <Download size={20} aria-hidden="true" />,
      items: [
        { label: 'Purchase Orders', to: '/purchase-orders', permission: 'purchase_orders_read', icon: <ShoppingCart size={18} /> },
        { label: 'GRN (Goods Receipt)', to: '/grn', permission: 'grn_read', icon: <Download size={18} /> },
      ],
    },
    {
      title: 'Sales',
      description: 'Quotations, orders, invoices',
      icon: <TrendingUp size={20} aria-hidden="true" />,
      items: [
        { label: 'Quotations', to: '/quotations', permission: 'quotations_read', icon: <FileText size={18} /> },
        { label: 'Sales Orders', to: '/sales-orders', permission: 'sales_orders_read', icon: <ShoppingCart size={18} /> },
        { label: 'Invoices', to: '/invoices', permission: 'sales_invoices_read', icon: <FileText size={18} /> },
      ],
    },
    {
      title: 'Payments',
      description: 'Receivables and payables',
      icon: <CreditCard size={20} aria-hidden="true" />,
      items: [
        { label: 'Receivables', to: '/receivables', permission: 'receipts_read', icon: <IndianRupee size={18} /> },
        { label: 'Payables', to: '/payables', permission: 'payments_read', icon: <CreditCard size={18} /> },
      ],
    },
    {
      title: 'Reporting',
      description: 'Analytics and insights',
      icon: <BarChart3 size={20} aria-hidden="true" />,
      items: [
        { label: 'Reports & Analytics', to: '/reports', permission: 'reports_read', icon: <BarChart3 size={18} /> },
      ],
    },
  ];

  const filteredSections = sections.map((section) => ({
    ...section,
    items: section.items.filter((item) => !item.permission || can(item.permission)),
  })).filter((section) => section.items.length > 0);

  const salesTrend = stats?.sales_trend || [];
  const topProducts = stats?.top_products || [];
  const recentInvoices = stats?.recent_invoices || [];

  return (
    <AppLayout title="Dashboard">
      <div className="space-y-6">
        {/* Financial KPI Cards */}
        <section className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
          <article className="hms-card p-5">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Today Sales</p>
                <p className="mt-2 text-2xl font-bold text-primary">{loading ? '-' : formatAmount(stats?.today_sales ?? 0)}</p>
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
                <TrendingUp size={18} className="text-primary" />
              </div>
            </div>
          </article>

          <article className="hms-card p-5">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Month Sales</p>
                <p className="mt-2 text-2xl font-bold text-primary">{loading ? '-' : formatAmount(stats?.month_sales ?? 0)}</p>
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-green-100">
                <IndianRupee size={18} className="text-green-600" />
              </div>
            </div>
          </article>

          <article className="hms-card p-5">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Outstanding Receivables</p>
                <p className="mt-2 text-2xl font-bold text-red-600">{loading ? '-' : formatAmount(stats?.outstanding_receivables ?? 0)}</p>
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-red-100">
                <AlertTriangle size={18} className="text-red-600" />
              </div>
            </div>
          </article>

          <article className="hms-card p-5">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Overdue Invoices</p>
                <p className="mt-2 text-2xl font-bold text-amber-600">{loading ? '-' : stats?.overdue_invoices_count ?? 0}</p>
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-amber-100">
                <AlertTriangle size={18} className="text-amber-600" />
              </div>
            </div>
          </article>
        </section>

        {/* Operations Stats Cards */}
        <section className="grid grid-cols-1 gap-4 md:grid-cols-3 lg:grid-cols-6">
          <article className="hms-card p-4">
            <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Products</p>
            <p className="mt-1 text-xl font-bold text-neutral-900">{loading ? '-' : stats?.total_products ?? 0}</p>
          </article>
          <article className="hms-card p-4">
            <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Customers</p>
            <p className="mt-1 text-xl font-bold text-neutral-900">{loading ? '-' : stats?.total_customers ?? 0}</p>
          </article>
          <article className="hms-card p-4">
            <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Suppliers</p>
            <p className="mt-1 text-xl font-bold text-neutral-900">{loading ? '-' : stats?.total_suppliers ?? 0}</p>
          </article>
          <article className="hms-card p-4">
            <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Low Stock</p>
            <p className="mt-1 text-xl font-bold text-amber-600">{loading ? '-' : stats?.low_stock_count ?? 0}</p>
          </article>
          <article className="hms-card p-4">
            <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Pending POs</p>
            <p className="mt-1 text-xl font-bold text-neutral-900">{loading ? '-' : stats?.pending_purchase_orders ?? 0}</p>
          </article>
          <article className="hms-card p-4">
            <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Pending SOs</p>
            <p className="mt-1 text-xl font-bold text-neutral-900">{loading ? '-' : stats?.pending_sales_orders ?? 0}</p>
          </article>
        </section>

        {/* Charts Row */}
        {!loading && salesTrend.length > 0 && (
          <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="hms-card p-6">
              <h3 className="mb-4 text-sm font-bold text-neutral-700">Sales Trend (Last 7 Days)</h3>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={salesTrend}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} tickFormatter={v => formatAmountShort(v)} />
                  <Tooltip formatter={(v: number) => formatAmount(v)} labelStyle={{ fontWeight: 600 }} />
                  <Line type="monotone" dataKey="amount" stroke="#1E3A5F" strokeWidth={2.5} dot={{ fill: '#1E3A5F', r: 4 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {topProducts.length > 0 && (
              <div className="hms-card p-6">
                <h3 className="mb-4 text-sm font-bold text-neutral-700">Top Selling Products</h3>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={topProducts.slice(0, 5)} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis type="number" tick={{ fontSize: 11 }} />
                    <YAxis dataKey="product_name" type="category" tick={{ fontSize: 11 }} width={100} />
                    <Tooltip formatter={(v: number) => formatAmount(v)} />
                    <Bar dataKey="amount" radius={[0, 4, 4, 0]}>
                      {topProducts.slice(0, 5).map((_, idx) => (
                        <Cell key={idx} fill={['#1E3A5F', '#2E86AB', '#22c55e', '#f59e0b', '#8b5cf6'][idx]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </section>
        )}

        {/* Recent Invoices */}
        {!loading && recentInvoices.length > 0 && (
          <section className="hms-card overflow-hidden">
            <div className="border-b border-neutral-200 bg-gradient-to-r from-neutral-50 to-white px-6 py-4">
              <h3 className="text-sm font-bold text-neutral-700">Recent Invoices</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="bg-neutral-50">
                  <th className="px-4 py-2 text-left font-semibold text-neutral-600">Invoice</th>
                  <th className="px-4 py-2 text-left font-semibold text-neutral-600">Customer</th>
                  <th className="px-4 py-2 text-right font-semibold text-neutral-600">Amount</th>
                  <th className="px-4 py-2 text-center font-semibold text-neutral-600">Status</th>
                  <th className="px-4 py-2 text-left font-semibold text-neutral-600">Date</th>
                </tr></thead>
                <tbody>
                  {recentInvoices.map((inv, idx) => (
                    <tr key={idx} className="border-t border-neutral-100">
                      <td className="px-4 py-2 font-medium">{inv.invoice_number}</td>
                      <td className="px-4 py-2">{inv.customer_name}</td>
                      <td className="px-4 py-2 text-right">{formatAmount(inv.amount)}</td>
                      <td className="px-4 py-2 text-center">
                        <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                          inv.status === 'paid' ? 'bg-green-100 text-green-700' :
                          inv.status === 'issued' ? 'bg-blue-100 text-blue-700' :
                          'bg-amber-100 text-amber-700'
                        }`}>{inv.status}</span>
                      </td>
                      <td className="px-4 py-2 text-neutral-500">{inv.date}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {/* Module Quick Links */}
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
                  key={item.label}
                  to={item.to}
                  className={quickLinkClassName}
                >
                  <span className="flex items-center gap-2">
                    <span className="text-neutral-500" aria-hidden="true">
                      {item.icon}
                    </span>
                    <span>{item.label}</span>
                  </span>
                  <ChevronRight size={16} className="text-neutral-400 transition group-hover:translate-x-1 group-hover:text-primary" />
                </Link>
              ))}
            </div>
          </section>
        ))}
      </div>
    </AppLayout>
  );
};

export default DashboardPage;
