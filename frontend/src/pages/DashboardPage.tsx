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
import { getDashboardStats, type DashboardStats as APIDashboardStats, type RevenueGeneration } from '../api/reports';
import { SubscriptionCard } from '../components/SubscriptionCard';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { FileQuestion } from 'lucide-react';

const formatAmount = (paise: number) => `₹${(paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
// Short daily label for the 7-day trend, e.g. "2026-07-31" -> "31 Jul".
const fmtDayLabel = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' });
};
const formatAmountShort = (paise: number) => {
  const val = paise / 100;
  if (val >= 100000) return `₹${(val / 100000).toFixed(1)}L`;
  if (val >= 1000) return `₹${(val / 1000).toFixed(1)}K`;
  return `₹${val.toFixed(0)}`;
};

// MCN-BUG-002: distinct colour per Sales Manager / Stockist
const REVENUE_COLORS = ['#1E3A5F', '#2563eb', '#16a34a', '#f59e0b', '#db2777', '#7c3aed', '#0891b2', '#dc2626', '#65a30d', '#ea580c', '#0d9488', '#9333ea'];

const REVENUE_VIEW_LABELS: Record<'daily' | 'weekly' | 'monthly', string> = {
  daily: 'Today',
  weekly: 'This Week',
  monthly: 'This Month',
};

const NoDataPlaceholder = ({ message }: { message: string }) => (
  <div className="flex h-full min-h-[150px] w-full flex-col items-center justify-center rounded-xl bg-neutral-50/50 border border-dashed border-neutral-200 p-6 text-center">
    <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-neutral-100/80">
      <FileQuestion size={20} className="text-neutral-400" />
    </div>
    <p className="max-w-[200px] text-xs font-semibold leading-relaxed text-neutral-500">{message}</p>
  </div>
);

// MCN-BUG-002: reusable revenue panel with an independent Day/Week/Month toggle.
const RevenuePanel = ({
  title,
  subtitle,
  data,
  loading,
  emptyMessage,
}: {
  title: string;
  subtitle: string;
  data?: RevenueGeneration;
  loading: boolean;
  emptyMessage: string;
}) => {
  const [view, setView] = useState<'daily' | 'weekly' | 'monthly'>('monthly');
  const rows = (data?.[view] || []).map((row, idx) => {
    const fullName = row.name || row.id.slice(0, 8);
    return {
      ...row,
      full_name: fullName,
      label: fullName.length > 14 ? `${fullName.slice(0, 14)}…` : fullName,
      color: REVENUE_COLORS[idx % REVENUE_COLORS.length],
    };
  });

  return (
    <div className="hms-card overflow-hidden p-6">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-bold text-neutral-700">{title}</h3>
          <p className="mt-0.5 text-xs text-neutral-500">{subtitle}</p>
        </div>
        <div className="flex rounded-lg border border-neutral-200 bg-neutral-50 p-1">
          {(['daily', 'weekly', 'monthly'] as const).map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setView(option)}
              className={`rounded-md px-3 py-1.5 text-xs font-semibold transition ${
                view === option ? 'bg-white text-primary shadow-sm' : 'text-neutral-600 hover:text-neutral-900'
              }`}
            >
              {option === 'daily' ? 'Day' : option === 'weekly' ? 'Week' : 'Month'}
            </button>
          ))}
        </div>
      </div>
      {!loading && rows.length > 0 ? (
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={rows} margin={{ top: 6, right: 8, left: 6, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="label" tick={{ fontSize: 11 }} interval={0} height={48} angle={-20} textAnchor="end" tickMargin={8} />
            <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => formatAmountShort(Number(v ?? 0))} />
            <Tooltip
              formatter={(value) => [formatAmount(Number(value ?? 0)), 'Revenue']}
              labelFormatter={(label, payload) => {
                const name = payload && payload.length ? (payload[0].payload.full_name as string) : label;
                return `${name} — ${REVENUE_VIEW_LABELS[view]}`;
              }}
              labelStyle={{ fontWeight: 600 }}
            />
            <Bar dataKey="revenue" name="Revenue" radius={[4, 4, 0, 0]}>
              {rows.map((row) => (
                <Cell key={row.id} fill={row.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      ) : (
        <NoDataPlaceholder message={emptyMessage} />
      )}
    </div>
  );
};

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
  const revenueGeneration = stats?.revenue_generation;

  return (
    <AppLayout title="Dashboard">
      <div className="space-y-6">
        {/* Current subscription plan — premium widget */}
        <SubscriptionCard />

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
          {/* Dashboard shows the last 7 days (daily). The Financial-Year trend with
              FY/Month filters lives on Reports → Sales Trend and is independent. */}
          <div className="hms-card p-6">
            <h3 className="mb-4 text-sm font-bold text-neutral-700">Sales Trend (Last 7 Days)</h3>
            {!loading && salesTrend.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={salesTrend}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={fmtDayLabel} />
                  <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => formatAmountShort(Number(v ?? 0))} />
                  <Tooltip formatter={(v) => formatAmount(Number(v ?? 0))} labelFormatter={(l) => fmtDayLabel(String(l))} labelStyle={{ fontWeight: 600 }} />
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
                    formatter={(value, name) => {
                      const numericValue = typeof value === 'number' ? value : Number(value ?? 0);
                      const label = typeof name === 'string' ? name : String(name ?? '');
                      if (label === 'fully_settled_amount' || label === 'Fully Received' || label === 'Fully Settled' || label === 'Fully Paid') {
                        return [formatAmount(numericValue), 'Fully Paid'];
                      }
                      if (label === 'partially_settled_amount' || label === 'Partially Received' || label === 'Partially Settled' || label === 'Partially Paid') {
                        return [formatAmount(numericValue), 'Partially Paid'];
                      }
                      return [formatAmount(numericValue), 'Received'];
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

        {/* MCN-BUG-002: Revenue Generation — Sales Manager (left) & Stockist (right) */}
        <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <RevenuePanel
            title="Sales Manager → Revenue Generation"
            subtitle="Revenue from issued invoices, by the user who raised them"
            data={revenueGeneration?.sales_manager}
            loading={loading}
            emptyMessage="No sales-manager revenue for the selected period yet."
          />
          <RevenuePanel
            title="Stockist → Revenue Generation"
            subtitle="Revenue from issued invoices, by stockist (customer)"
            data={revenueGeneration?.stockist}
            loading={loading}
            emptyMessage="No stockist revenue for the selected period yet."
          />
        </section>

      </div>
    </AppLayout>
  );
};

export default DashboardPage;
