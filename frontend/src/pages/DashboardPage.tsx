/**
 * Dashboard Page
 *
 * Main page after login - shows KPIs, charts, and navigation.
 */

import { AppLayout } from '../components/AppLayout';
import {
  AlertTriangle,
  TrendingUp,
  IndianRupee,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { getDashboardStats, type DashboardStats as APIDashboardStats } from '../api/reports';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { FileQuestion } from 'lucide-react';

const NoDataPlaceholder = ({ message }: { message: string }) => (
  <div className="flex h-full min-h-[150px] w-full flex-col items-center justify-center rounded-xl bg-neutral-50/50 border border-dashed border-neutral-200 p-6 text-center">
    <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-neutral-100/80">
      <FileQuestion size={20} className="text-neutral-400" />
    </div>
    <p className="max-w-[200px] text-xs font-semibold leading-relaxed text-neutral-500">{message}</p>
  </div>
);

const DashboardPage = () => {
  const [stats, setStats] = useState<APIDashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [cashInFlowView, setCashInFlowView] = useState<'daily' | 'weekly' | 'monthly'>('daily');

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



  const salesTrend = stats?.sales_trend || [];
  const cashInFlowRows = stats?.cash_in_flow?.[cashInFlowView] || [];
  const cashInFlowSummary = stats?.cash_in_flow_summary?.[cashInFlowView] || {
    total_received_amount: 0,
    fully_settled_amount: 0,
    partially_settled_amount: 0,
  };
  const cashInFlow = cashInFlowRows.map((item) => ({
    ...item,
    customer_label: (item.customer_name || item.customer_id.slice(0, 8)).length > 14
      ? `${(item.customer_name || item.customer_id.slice(0, 8)).slice(0, 14)}...`
      : (item.customer_name || item.customer_id.slice(0, 8)),
    customer_full_name: item.customer_name || item.customer_id.slice(0, 8),
  }));
  const recentInvoices = stats?.recent_invoices || [];

  const toTitleCase = (value: string) =>
    value
      .replace(/_/g, ' ')
      .toLowerCase()
      .replace(/\b\w/g, (ch) => ch.toUpperCase());

  const dashboardInvoiceStatusLabel = (status: string) => {
    const token = (status || '').trim().toLowerCase();
    if (token === 'issued') return 'Issued';
    if (token === 'partial_paid') return 'Partially Paid';
    if (token === 'paid') return 'Fully Paid';
    if (token === 'draft') return 'Draft';
    if (token === 'cancelled') return 'Cancelled';
    return toTitleCase(token || '-');
  };

  const dashboardInvoiceStatusClass = (status: string) => {
    const token = (status || '').trim().toLowerCase();
    if (token === 'paid') return 'bg-green-100 text-green-700';
    if (token === 'issued') return 'bg-blue-100 text-blue-700';
    if (token === 'partial_paid') return 'bg-amber-100 text-amber-700';
    if (token === 'cancelled') return 'bg-red-100 text-red-700';
    return 'bg-gray-100 text-gray-700';
  };

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
            <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Below Safety</p>
            <p className="mt-1 text-xl font-bold text-amber-600">{loading ? '-' : stats?.safety_stock_count ?? 0}</p>
          </article>
          <article className="hms-card p-4">
            <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Low Stock</p>
            <p className="mt-1 text-xl font-bold text-red-600">{loading ? '-' : stats?.low_stock_count ?? 0}</p>
          </article>
          <article className="hms-card p-4">
            <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Pending POs</p>
            <p className="mt-1 text-xl font-bold text-neutral-900">{loading ? '-' : stats?.pending_purchase_orders ?? 0}</p>
          </article>
        </section>

        {/* Charts Row */}
        <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <div className="hms-card p-6">
            <h3 className="mb-4 text-sm font-bold text-neutral-700">Sales Trend (Last 7 Days)</h3>
            {!loading && salesTrend.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={salesTrend}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} tickFormatter={v => formatAmountShort(v)} />
                  <Tooltip formatter={(v: number) => formatAmount(v)} labelStyle={{ fontWeight: 600 }} />
                  <Line type="monotone" dataKey="amount" stroke="#1E3A5F" strokeWidth={2.5} dot={{ fill: '#1E3A5F', r: 4 }} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <NoDataPlaceholder message="No sales trend data available yet. Start creating invoices to see growth." />
            )}
          </div>

          <div className="hms-card overflow-hidden p-6">
            <div className="mb-4 flex items-center justify-between gap-3">
              <h3 className="text-sm font-bold text-neutral-700">Cash In Flow Graph (Received Receipts)</h3>
              <div className="flex rounded-lg border border-neutral-200 bg-neutral-50 p-1">
                {(['daily', 'weekly', 'monthly'] as const).map((view) => (
                  <button
                    key={view}
                    type="button"
                    onClick={() => setCashInFlowView(view)}
                    className={`rounded-md px-3 py-1.5 text-xs font-semibold transition ${
                      cashInFlowView === view
                        ? 'bg-white text-primary shadow-sm'
                        : 'text-neutral-600 hover:text-neutral-900'
                    }`}
                  >
                    {view.charAt(0).toUpperCase() + view.slice(1)}
                  </button>
                ))}
              </div>
            </div>
            <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-3">
              <div className="rounded-lg border border-neutral-200 bg-white px-3 py-2">
                <p className="text-xs font-semibold text-neutral-600">Total Received</p>
                <p className="mt-1 text-sm font-semibold text-primary">{formatAmount(cashInFlowSummary.total_received_amount)}</p>
              </div>
              <div className="rounded-lg border border-green-200 bg-green-50 px-3 py-2">
                <p className="text-xs font-semibold text-green-700">Fully Paid</p>
                <p className="mt-1 text-sm font-semibold text-green-700">{formatAmount(cashInFlowSummary.fully_settled_amount)}</p>
              </div>
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2">
                <p className="text-xs font-semibold text-amber-700">Partially Paid</p>
                <p className="mt-1 text-sm font-semibold text-amber-700">{formatAmount(cashInFlowSummary.partially_settled_amount)}</p>
              </div>
            </div>
            {!loading && cashInFlow.length > 0 ? (
              <>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={cashInFlow} margin={{ top: 6, right: 8, left: 6, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis
                    dataKey="customer_label"
                    tick={{ fontSize: 11 }}
                    interval="preserveStartEnd"
                    height={44}
                    tickMargin={8}
                  />
                  <YAxis
                    tick={{ fontSize: 11 }}
                    tickFormatter={(v) => formatAmountShort(v)}
                  />
                  <Tooltip
                    formatter={(value: number, name: string) => {
                      if (name === 'fully_settled_amount' || name === 'Fully Received' || name === 'Fully Settled' || name === 'Fully Paid') {
                        return [formatAmount(value), 'Fully Paid'];
                      }
                      if (name === 'partially_settled_amount' || name === 'Partially Received' || name === 'Partially Settled' || name === 'Partially Paid') {
                        return [formatAmount(value), 'Partially Paid'];
                      }
                      return [formatAmount(value), 'Received'];
                    }}
                    labelStyle={{ fontWeight: 600 }}
                  />
                  <Bar dataKey="partially_settled_amount" name="Partially Paid" stackId="received" fill="#f59e0b" radius={[0, 0, 0, 0]} />
                  <Bar dataKey="fully_settled_amount" name="Fully Paid" stackId="received" fill="#16a34a" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
              <div className="mt-3 flex flex-wrap items-center gap-4 text-xs font-semibold text-neutral-600">
                <span className="inline-flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full bg-green-600" />
                  Fully Paid
                </span>
                <span className="inline-flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full bg-amber-500" />
                  Partially Paid
                </span>
              </div>
              </>
            ) : (
              <NoDataPlaceholder message="No customer receipts found for selected period in Cash In Flow graph." />
            )}
          </div>
        </section>

        {/* Recent Invoices */}
        <section className="hms-card overflow-hidden">
          <div className="border-b border-neutral-200 bg-gradient-to-r from-neutral-50 to-white px-6 py-4">
            <h3 className="text-sm font-bold text-neutral-700">Recent Invoices</h3>
          </div>
          {!loading && recentInvoices.length > 0 ? (
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
                        <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${dashboardInvoiceStatusClass(inv.status)}`}>
                          {dashboardInvoiceStatusLabel(inv.status)}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-neutral-500">{inv.date}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-8">
              <NoDataPlaceholder message="No recent invoices found. Once you issue your first tax invoice, it will appear here." />
            </div>
          )}
        </section>

      </div>
    </AppLayout>
  );
};

export default DashboardPage;
