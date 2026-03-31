/**
 * Reports Page
 * Visual analytics hub with charts, tables, and financial summaries.
 * Uses Recharts for data visualization.
 */
import { useState, useEffect } from 'react';
import { AppLayout } from '../components/AppLayout';
import { BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { apiClient } from '../api/client';

interface PLData { net_sales: number; purchases: number; gross_profit: number; gross_profit_margin_percent: number; net_profit: number; }
interface StockItem { product_code: string; product_name: string; closing_qty: number; min_stock: number; status: string; }
interface SalesReportItem { invoice_number: string; invoice_date: string; total_amount: number; amount_paid: number; amount_due: number; status: string; }
interface GSTData { summary: { total_taxable: number; total_cgst: number; total_sgst: number; total_igst: number }; count: number; }
interface GSTR3BData { output_tax: number; itc: number; net_tax_payable: number; }

const formatAmount = (p: number) => `₹${(p / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;

const ReportsPage = () => {
  const today = new Date();
  const monthStart = new Date(today.getFullYear(), today.getMonth(), 1);
  const [fromDate, setFromDate] = useState(monthStart.toISOString().split('T')[0]);
  const [toDate, setToDate] = useState(today.toISOString().split('T')[0]);
  const [activeTab, setActiveTab] = useState<'overview' | 'sales' | 'stock' | 'gst' | 'pl'>('overview');
  const [loading, setLoading] = useState(false);

  // Data
  const [dashboard, setDashboard] = useState<Record<string, unknown> | null>(null);
  const [plData, setPLData] = useState<PLData | null>(null);
  const [stockItems, setStockItems] = useState<StockItem[]>([]);
  const [salesItems, setSalesItems] = useState<SalesReportItem[]>([]);
  const [salesTotal, setSalesTotal] = useState(0);
  const [gstData, setGstData] = useState<GSTData | null>(null);
  const [gstr3bData, setGstr3bData] = useState<GSTR3BData | null>(null);

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [dashRes, plRes, stockRes, salesRes, gstRes, gstr3bRes] = await Promise.all([
        apiClient.get('/api/v1/reports/dashboard').catch(() => ({ data: null })),
        apiClient.get('/api/v1/reports/pl', { params: { from_date: fromDate, to_date: toDate } }).catch(() => ({ data: null })),
        apiClient.get('/api/v1/reports/stock').catch(() => ({ data: { items: [] } })),
        apiClient.get('/api/v1/reports/sales', { params: { from_date: fromDate, to_date: toDate } }).catch(() => ({ data: { items: [], total_amount: 0 } })),
        apiClient.get('/api/v1/reports/gstr1', { params: { from_date: fromDate, to_date: toDate } }).catch(() => ({ data: null })),
        apiClient.get('/api/v1/reports/gstr3b', { params: { from_date: fromDate, to_date: toDate } }).catch(() => ({ data: null })),
      ]);
      setDashboard(dashRes.data);
      setPLData(plRes.data);
      setStockItems(stockRes.data?.items || []);
      setSalesItems(salesRes.data?.items || []);
      setSalesTotal(salesRes.data?.total_amount || 0);
      setGstData(gstRes.data);
      setGstr3bData(gstr3bRes.data);
    } catch { /* */ }
    setLoading(false);
  };

  useEffect(() => { fetchAll(); }, [fromDate, toDate]);

  const salesTrend = (dashboard as Record<string, unknown>)?.sales_trend as { date: string; amount: number }[] || [];
  const topProducts = (dashboard as Record<string, unknown>)?.top_products as { product_name: string; quantity_sold: number; amount: number }[] || [];

  const stockSummary = [
    { name: 'Normal', value: stockItems.filter(i => i.status === 'Normal').length },
    { name: 'Below Safety Stock', value: stockItems.filter(i => i.status === 'Below Safety Stock').length },
    { name: 'Low Stock', value: stockItems.filter(i => i.status === 'Low Stock').length },
    { name: 'Out of Stock', value: stockItems.filter(i => i.status === 'Out of Stock').length },
  ].filter(i => i.value > 0);

  const tabs = [
    { key: 'overview', label: 'Overview' },
    { key: 'sales', label: 'Sales Report' },
    { key: 'stock', label: 'Stock Report' },
    { key: 'gst', label: 'GST Report' },
    { key: 'pl', label: 'Profit & Loss' },
  ] as const;

  return (
    <AppLayout title="Reports & Analytics">
      <div className="space-y-6">
        {/* Date Range + Tabs */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            {tabs.map(t => (
              <button key={t.key} onClick={() => setActiveTab(t.key)}
                className={`rounded-lg px-4 py-2 text-sm font-semibold transition ${activeTab === t.key ? 'bg-primary text-white' : 'bg-white text-neutral-600 border border-neutral-200 hover:bg-neutral-50'}`}
              >{t.label}</button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <input type="date" className="rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={fromDate} onChange={e => setFromDate(e.target.value)} />
            <span className="text-sm text-neutral-500">to</span>
            <input type="date" className="rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={toDate} onChange={e => setToDate(e.target.value)} />
          </div>
        </div>

        {loading && <div className="py-12 text-center text-neutral-500">Loading reports...</div>}

        {/* Overview Tab */}
        {!loading && activeTab === 'overview' && (
          <div className="space-y-6">
            {/* KPI Cards */}
            <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
              <div className="hms-card p-5">
                <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Today Sales</p>
                <p className="mt-2 text-2xl font-bold text-primary">{formatAmount(Number((dashboard as Record<string, unknown>)?.today_sales) || 0)}</p>
              </div>
              <div className="hms-card p-5">
                <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Month Sales</p>
                <p className="mt-2 text-2xl font-bold text-primary">{formatAmount(Number((dashboard as Record<string, unknown>)?.month_sales) || 0)}</p>
              </div>
              <div className="hms-card p-5">
                <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Outstanding Receivables</p>
                <p className="mt-2 text-2xl font-bold text-red-600">{formatAmount(Number((dashboard as Record<string, unknown>)?.outstanding_receivables) || 0)}</p>
              </div>
              <div className="hms-card p-5">
                <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Overdue Invoices</p>
                <p className="mt-2 text-2xl font-bold text-amber-600">{Number((dashboard as Record<string, unknown>)?.overdue_invoices_count) || 0}</p>
              </div>
            </div>

            {/* Charts Row */}
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              {/* Sales Trend */}
              <div className="hms-card p-6">
                <h3 className="mb-4 text-sm font-bold text-neutral-700">Sales Trend (Last 7 Days)</h3>
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart data={salesTrend}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 12 }} tickFormatter={v => `₹${(v/100).toFixed(0)}`} />
                    <Tooltip formatter={(v: number) => formatAmount(v)} />
                    <Line type="monotone" dataKey="amount" stroke="#1E3A5F" strokeWidth={2} dot={{ fill: '#1E3A5F' }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              {/* Stock Distribution */}
              <div className="hms-card p-6">
                <h3 className="mb-4 text-sm font-bold text-neutral-700">Stock Status Distribution</h3>
                <ResponsiveContainer width="100%" height={250}>
                  <PieChart>
                    <Pie data={stockSummary} cx="50%" cy="50%" labelLine={false} label={({ name, value }) => `${name}: ${value}`}
                      outerRadius={80} dataKey="value">
                      {stockSummary.map((_, idx) => <Cell key={idx} fill={['#22c55e', '#38bdf8', '#f59e0b', '#ef4444'][idx]} />)}
                    </Pie>
                    <Tooltip />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Top Products */}
            {topProducts.length > 0 && (
              <div className="hms-card p-6">
                <h3 className="mb-4 text-sm font-bold text-neutral-700">Top Selling Products (This Month)</h3>
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={topProducts}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis dataKey="product_name" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Bar dataKey="quantity_sold" fill="#2E86AB" name="Qty Sold" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        )}

        {/* Sales Report Tab */}
        {!loading && activeTab === 'sales' && (
          <div className="space-y-4">
            <div className="hms-card p-5">
              <p className="text-sm text-neutral-500">Total Sales ({fromDate} to {toDate})</p>
              <p className="mt-1 text-2xl font-bold text-primary">{formatAmount(salesTotal)}</p>
              <p className="text-xs text-neutral-500">{salesItems.length} invoice(s)</p>
            </div>
            <div className="hms-card overflow-hidden">
              <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b bg-neutral-50"><th className="px-4 py-3 text-left font-semibold">Invoice #</th><th className="px-4 py-3 text-left font-semibold">Date</th><th className="px-4 py-3 text-right font-semibold">Amount</th><th className="px-4 py-3 text-right font-semibold">Paid</th><th className="px-4 py-3 text-right font-semibold">Due</th><th className="px-4 py-3 text-center font-semibold">Status</th></tr></thead>
                <tbody>{salesItems.map((i, idx) => (<tr key={idx} className="border-b border-neutral-100"><td className="px-4 py-3">{i.invoice_number}</td><td className="px-4 py-3">{i.invoice_date}</td><td className="px-4 py-3 text-right">{formatAmount(i.total_amount)}</td><td className="px-4 py-3 text-right text-green-600">{formatAmount(i.amount_paid)}</td><td className="px-4 py-3 text-right text-red-600">{i.amount_due > 0 ? formatAmount(i.amount_due) : '-'}</td><td className="px-4 py-3 text-center"><span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-semibold text-blue-700">{i.status}</span></td></tr>))}</tbody>
              </table></div>
            </div>
          </div>
        )}

        {/* Stock Report Tab */}
        {!loading && activeTab === 'stock' && (
          <div className="hms-card overflow-hidden">
            <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b bg-neutral-50"><th className="px-4 py-3 text-left font-semibold">Code</th><th className="px-4 py-3 text-left font-semibold">Product</th><th className="px-4 py-3 text-right font-semibold">Qty</th><th className="px-4 py-3 text-right font-semibold">Min</th><th className="px-4 py-3 text-center font-semibold">Status</th></tr></thead>
              <tbody>{stockItems.map((i, idx) => {
                const sc: Record<string, string> = {
                  'Normal': 'bg-green-100 text-green-700',
                  'Below Safety Stock': 'bg-sky-100 text-sky-700',
                  'Low Stock': 'bg-amber-100 text-amber-700',
                  'Out of Stock': 'bg-red-100 text-red-700'
                };
                return (<tr key={idx} className="border-b border-neutral-100"><td className="px-4 py-3">{i.product_code}</td><td className="px-4 py-3">{i.product_name}</td><td className="px-4 py-3 text-right">{i.closing_qty}</td><td className="px-4 py-3 text-right text-neutral-500">{i.min_stock}</td><td className="px-4 py-3 text-center"><span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${sc[i.status]}`}>{i.status}</span></td></tr>);
              })}</tbody>
            </table></div>
            <p className="border-t px-4 py-3 text-xs text-neutral-500">{stockItems.length} products</p>
          </div>
        )}

        {/* GST Report Tab */}
        {!loading && activeTab === 'gst' && (
          <div className="space-y-6">
            {gstData && (
              <div className="hms-card p-6">
                <h3 className="mb-4 text-sm font-bold text-neutral-700">GSTR-1 Summary (Output Tax)</h3>
                <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                  <div><p className="text-xs text-neutral-500">Taxable Value</p><p className="text-lg font-bold">{formatAmount(gstData.summary.total_taxable)}</p></div>
                  <div><p className="text-xs text-neutral-500">CGST</p><p className="text-lg font-bold">{formatAmount(gstData.summary.total_cgst)}</p></div>
                  <div><p className="text-xs text-neutral-500">SGST</p><p className="text-lg font-bold">{formatAmount(gstData.summary.total_sgst)}</p></div>
                  <div><p className="text-xs text-neutral-500">IGST</p><p className="text-lg font-bold">{formatAmount(gstData.summary.total_igst)}</p></div>
                </div>
                <p className="mt-2 text-xs text-neutral-500">{gstData.count} invoice(s)</p>
              </div>
            )}
            {gstr3bData && (
              <div className="hms-card p-6">
                <h3 className="mb-4 text-sm font-bold text-neutral-700">GSTR-3B Summary (Tax Liability)</h3>
                <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                  <div className="rounded-lg bg-blue-50 p-4"><p className="text-xs text-blue-600">Output Tax</p><p className="text-xl font-bold text-blue-800">{formatAmount(gstr3bData.output_tax)}</p></div>
                  <div className="rounded-lg bg-green-50 p-4"><p className="text-xs text-green-600">Input Tax Credit (ITC)</p><p className="text-xl font-bold text-green-800">{formatAmount(gstr3bData.itc)}</p></div>
                  <div className="rounded-lg bg-amber-50 p-4"><p className="text-xs text-amber-600">Net Tax Payable</p><p className="text-xl font-bold text-amber-800">{formatAmount(gstr3bData.net_tax_payable)}</p></div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* P&L Tab */}
        {!loading && activeTab === 'pl' && plData && (
          <div className="space-y-6">
            <div className="hms-card p-6">
              <h3 className="mb-6 text-sm font-bold text-neutral-700">Profit & Loss Statement</h3>
              <div className="space-y-4">
                <div className="flex items-center justify-between border-b pb-3">
                  <span className="text-sm font-semibold text-neutral-600">Net Sales</span>
                  <span className="text-lg font-bold text-green-600">{formatAmount(plData.net_sales)}</span>
                </div>
                <div className="flex items-center justify-between border-b pb-3">
                  <span className="text-sm font-semibold text-neutral-600">Less: Purchases</span>
                  <span className="text-lg font-bold text-red-600">({formatAmount(plData.purchases)})</span>
                </div>
                <div className="flex items-center justify-between border-b-2 border-primary/20 pb-3">
                  <span className="text-sm font-bold text-primary">Gross Profit</span>
                  <span className={`text-xl font-bold ${plData.gross_profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>{formatAmount(plData.gross_profit)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-neutral-500">Gross Profit Margin</span>
                  <span className="text-lg font-bold text-primary">{plData.gross_profit_margin_percent}%</span>
                </div>
              </div>
            </div>

            {/* P&L Visual */}
            <div className="hms-card p-6">
              <h3 className="mb-4 text-sm font-bold text-neutral-700">Revenue vs Purchases</h3>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={[{ name: 'Sales', value: plData.net_sales }, { name: 'Purchases', value: plData.purchases }, { name: 'Profit', value: plData.gross_profit }]}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} tickFormatter={v => `₹${(v/100/1000).toFixed(0)}K`} />
                  <Tooltip formatter={(v: number) => formatAmount(v)} />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                    {[0, 1, 2].map(idx => <Cell key={idx} fill={['#22c55e', '#ef4444', '#1E3A5F'][idx]} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
};

export default ReportsPage;
