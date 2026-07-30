/**
 * SalesTrendChart (MCN-BUG-01)
 *
 * Financial-Year (April → March) sales trend line chart with a Financial Year
 * selector and a Month selector. Selecting a month drills into that month's daily
 * totals; otherwise 12 months are shown in FY order (Apr..Mar). Data is fetched
 * from /reports/sales-trend, which is tenant-scoped on the backend.
 */
import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { getSalesTrend } from '../api/reports';
import { useAuthStore } from '../store/auth';

const FY_MONTHS = [
  { value: 4, label: 'April' }, { value: 5, label: 'May' }, { value: 6, label: 'June' },
  { value: 7, label: 'July' }, { value: 8, label: 'August' }, { value: 9, label: 'September' },
  { value: 10, label: 'October' }, { value: 11, label: 'November' }, { value: 12, label: 'December' },
  { value: 1, label: 'January' }, { value: 2, label: 'February' }, { value: 3, label: 'March' },
];

const currentFyStart = (): number => {
  const d = new Date();
  return d.getMonth() + 1 >= 4 ? d.getFullYear() : d.getFullYear() - 1;
};

const fyLabel = (start: number) => `${start}-${String(start + 1).slice(-2)}`;

const formatAmount = (paise: number) => `₹${(paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
const formatShort = (paise: number) => {
  const r = paise / 100;
  if (r >= 10000000) return `₹${(r / 10000000).toFixed(1)}Cr`;
  if (r >= 100000) return `₹${(r / 100000).toFixed(1)}L`;
  if (r >= 1000) return `₹${(r / 1000).toFixed(1)}K`;
  return `₹${r.toFixed(0)}`;
};

export function SalesTrendChart() {
  const companyId = useAuthStore((s) => s.user?.company_id ?? null);
  const [fy, setFy] = useState<number>(currentFyStart());
  const [month, setMonth] = useState<number | ''>('');

  // Offer the current FY and the previous four (historical financial years).
  const fyOptions = useMemo(() => {
    const cur = currentFyStart();
    return [0, 1, 2, 3, 4].map((n) => cur - n);
  }, []);

  const query = useQuery({
    queryKey: ['sales-trend', companyId, fy, month === '' ? null : month],
    queryFn: () => getSalesTrend(fy, month === '' ? undefined : month),
    staleTime: 60 * 1000,
  });

  const points = query.data?.points ?? [];
  const hasData = points.some((p) => p.amount > 0);

  return (
    <div className="hms-card p-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-bold text-neutral-700">
          Sales Trend — FY {query.data?.financial_year_label ?? fyLabel(fy)}
          {month !== '' && ` · ${FY_MONTHS.find((m) => m.value === month)?.label}`}
        </h3>
        <div className="flex flex-wrap gap-2">
          <select
            value={fy}
            onChange={(e) => setFy(Number(e.target.value))}
            className="rounded-lg border border-neutral-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-neutral-700 focus:border-primary focus:outline-none"
            aria-label="Financial Year"
          >
            {fyOptions.map((y) => <option key={y} value={y}>FY {fyLabel(y)}</option>)}
          </select>
          <select
            value={month}
            onChange={(e) => setMonth(e.target.value === '' ? '' : Number(e.target.value))}
            className="rounded-lg border border-neutral-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-neutral-700 focus:border-primary focus:outline-none"
            aria-label="Month"
          >
            <option value="">All Months</option>
            {FY_MONTHS.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
          </select>
        </div>
      </div>

      {query.isLoading ? (
        <div className="flex h-[220px] items-center justify-center text-sm text-neutral-400">Loading…</div>
      ) : hasData ? (
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={points}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="label" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => formatShort(Number(v))} />
            <Tooltip formatter={(v) => formatAmount(Number(v ?? 0))} labelStyle={{ fontWeight: 600 }} />
            <Line type="monotone" dataKey="amount" stroke="#1E3A5F" strokeWidth={2.5} dot={{ fill: '#1E3A5F', r: 3 }} />
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <div className="flex h-[220px] items-center justify-center text-center text-sm text-neutral-400">
          No sales in FY {fyLabel(fy)}{month !== '' ? ` · ${FY_MONTHS.find((m) => m.value === month)?.label}` : ''}.
        </div>
      )}
    </div>
  );
}
