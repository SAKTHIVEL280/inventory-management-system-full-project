/**
 * Stock / Inventory Page
 * View current stock levels, low stock alerts.
 */
import { useState, useEffect } from 'react';
import { AppLayout } from '../components/AppLayout';
import { getStockReport, type StockReportItem } from '../api/reports';

const StockPage = () => {
  const [items, setItems] = useState<StockReportItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [lowStockOnly, setLowStockOnly] = useState(false);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  const fetchStock = async () => {
    try {
      setLoading(true);
      const data = await getStockReport(lowStockOnly);
      setItems(data.items || []);
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps -- fetchStock should run when lowOnly/archiveView filters change
  useEffect(() => { fetchStock(); }, [lowStockOnly, statusFilter]);

  const filtered = items.filter(i => {
    const q = search.trim().toLowerCase();
    const matchesSearch =
      !q ||
      i.product_name.toLowerCase().includes(q) ||
      i.product_code.toLowerCase().includes(q) ||
      (i.batch_no || '').toLowerCase().includes(q) ||
      i.hsn.toLowerCase().includes(q) ||
      i.status.toLowerCase().includes(q);
    const matchesStatus = !statusFilter || i.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const formatDate = (value: string | null) => {
    if (!value) return '—';
    const [year, month, day] = value.split('-');
    if (!year || !month || !day) return value;
    return `${day}-${month}-${year}`;
  };

  const sc: Record<string, string> = {
    'In Stock': 'bg-green-100 text-green-700',
    'Low Stock': 'bg-orange-100 text-orange-700 animate-pulse',
  };

  const lowCount = items.filter(i => i.status === 'Low Stock').length;
  const normalCount = items.filter(i => i.status === 'In Stock').length;

  return (
    <AppLayout title="Stock / Inventory">
      <div className="space-y-6">
        {/* Summary Cards */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="hms-card p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">In Stock Rows</p>
                <p className="mt-2 text-2xl font-bold text-green-600">{normalCount}</p>
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-green-100">
                <span className="material-icons text-green-600" aria-hidden="true">check_circle</span>
              </div>
            </div>
          </div>
          <div className="hms-card p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Low Stock Rows</p>
                <p className="mt-2 text-2xl font-bold text-orange-600">{lowCount}</p>
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-orange-100">
                <span className="material-icons text-orange-600" aria-hidden="true">warning</span>
              </div>
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3">
          <input
            type="text" placeholder="Search by name, code, batch, HSN, status..."
            className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm w-64"
            value={search} onChange={e => setSearch(e.target.value)}
          />
          <select
            className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm"
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
          >
            <option value="">All Statuses</option>
            <option value="In Stock">In Stock</option>
            <option value="Low Stock">Low Stock</option>
          </select>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={lowStockOnly} onChange={e => setLowStockOnly(e.target.checked)} className="rounded" />
            <span>Low/Out of Stock only</span>
          </label>
        </div>

        {/* Table */}
        <div className="hms-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-neutral-200 bg-neutral-50">
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Code</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Product Name</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Batch No</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">MFG Date</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">EXP Date</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">HSN</th>
                <th className="px-4 py-3 text-right font-semibold text-neutral-600">Current Qty</th>
                <th className="px-4 py-3 text-right font-semibold text-neutral-600">Safety Stock</th>
                <th className="px-4 py-3 text-right font-semibold text-neutral-600">Min Stock</th>
                <th className="px-4 py-3 text-center font-semibold text-neutral-600">Status</th>
              </tr></thead>
              <tbody>
                {loading ? <tr><td colSpan={10} className="px-4 py-8 text-center text-neutral-500">Loading...</td></tr>
                : filtered.length === 0 ? <tr><td colSpan={10} className="px-4 py-8 text-center text-neutral-500">No stock rows found</td></tr>
                : filtered.map((item, idx) => (
                  <tr key={`${item.product_code}-${item.batch_no || 'no-batch'}-${idx}`} className="border-b border-neutral-100 hover:bg-neutral-50">
                    <td className="px-4 py-3 font-medium">{item.product_code}</td>
                    <td className="px-4 py-3">{item.product_name}</td>
                    <td className="px-4 py-3 text-neutral-700">{item.batch_no || <span className="text-neutral-300">—</span>}</td>
                    <td className="px-4 py-3 text-neutral-500">{formatDate(item.manufacture_date)}</td>
                    <td className="px-4 py-3 text-neutral-500">{formatDate(item.expiry_date)}</td>
                    <td className="px-4 py-3 text-neutral-500">{item.hsn}</td>
                    <td className="px-4 py-3 text-right font-medium">{item.closing_qty}</td>
                    <td className="px-4 py-3 text-right text-neutral-500">{item.safety_stock}</td>
                    <td className="px-4 py-3 text-right text-neutral-500">{item.min_stock}</td>
                    <td className="px-4 py-3 text-center">
                      <span className={`inline-block rounded-full px-2.5 py-1 text-xs font-semibold ${sc[item.status] || 'bg-gray-100'}`}>{item.status}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!loading && <p className="border-t border-neutral-200 px-4 py-3 text-xs text-neutral-500">Showing {filtered.length} of {items.length} stock rows</p>}
        </div>
      </div>
    </AppLayout>
  );
};

export default StockPage;
