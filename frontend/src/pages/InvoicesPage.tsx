/**
 * Sales Invoices Page
 * List, create, edit, issue invoices. GST-aware line items.
 */
import { useState, useEffect } from 'react';
import { AppLayout } from '../components/AppLayout';
import { salesApi, type SalesInvoice, type CreateInvoicePayload, type SalesLineItem } from '../api/sales';
import { apiClient } from '../api/client';
import { toast } from 'sonner';

interface ProductOption { id: string; name: string; product_code: string; selling_price: number; gst_rate: number; }
interface CustomerOption { id: string; company_name: string; customer_code: string; }

const InvoicesPage = () => {
  const [invoices, setInvoices] = useState<SalesInvoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState('');
  const [customers, setCustomers] = useState<CustomerOption[]>([]);
  const [products, setProducts] = useState<ProductOption[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const [customerId, setCustomerId] = useState('');
  const [invoiceDate, setInvoiceDate] = useState(new Date().toISOString().split('T')[0]);
  const [dueDate, setDueDate] = useState('');
  const [notes, setNotes] = useState('');
  const [items, setItems] = useState<SalesLineItem[]>([]);
  const [soNumberSearch, setSoNumberSearch] = useState('');
  const [isSearchingSO, setIsSearchingSO] = useState(false);
  const [soId, setSoId] = useState<string | undefined>(undefined);

  const fetchInvoices = async () => {
    try { setLoading(true); const res = await salesApi.listInvoices(statusFilter || undefined); setInvoices(res.data.items || []); } catch { setError('Failed to load'); } finally { setLoading(false); }
  };
  const fetchMasterData = async () => {
    try { const [c, p] = await Promise.all([apiClient.get('/api/v1/customers', { params: { page_size: 100 } }), apiClient.get('/api/v1/products', { params: { page_size: 100 } })]); setCustomers(c.data.items || []); setProducts(p.data.items || []); } catch { /* */ }
  };

  useEffect(() => { fetchInvoices(); }, [statusFilter]);
  useEffect(() => { fetchMasterData(); }, []);

  const resetForm = () => { setCustomerId(''); setInvoiceDate(new Date().toISOString().split('T')[0]); setDueDate(''); setNotes(''); setItems([]); setEditingId(null); setError(''); setSoNumberSearch(''); setSoId(undefined); };
  const addItem = () => { setItems([...items, { product_id: '', quantity: 1, unit_price: 0, discount_percent: 0, gst_rate: 18 }]); };
  const updateItem = (idx: number, field: keyof SalesLineItem, value: string | number) => {
    const updated = [...items]; (updated[idx] as unknown as Record<string, unknown>)[field] = value;
    if (field === 'product_id') { const p = products.find(x => x.id === value); if (p) { updated[idx].unit_price = p.selling_price; updated[idx].gst_rate = p.gst_rate; } }
    setItems(updated);
  };
  const removeItem = (idx: number) => { setItems(items.filter((_, i) => i !== idx)); };
  const calcTotal = (i: SalesLineItem) => { const g = i.unit_price * i.quantity; const d = g * (i.discount_percent || 0) / 100; const t = g - d; return t + t * i.gst_rate / 100; };
  const formatAmount = (p: number) => `₹${(p / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;

  const handleSubmit = async () => {
    if (!customerId || items.length === 0) { setError('Select customer & add items'); return; }
    setSubmitting(true); setError('');
    try {
      const payload: CreateInvoicePayload = {
        customer_id: customerId, sales_order_id: soId, invoice_date: invoiceDate, due_date: dueDate || undefined,
        bill_to_customer_id: customerId, notes: notes || undefined,
        items: items.map(i => ({ product_id: i.product_id, quantity: Number(i.quantity), unit_price: Number(i.unit_price), discount_percent: Number(i.discount_percent || 0), gst_rate: Number(i.gst_rate) })),
      };
      if (editingId) await salesApi.updateInvoice(editingId, payload); else await salesApi.createInvoice(payload);
      setShowForm(false); resetForm(); fetchInvoices();
    } catch (err: unknown) { const m = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail; setError(typeof m === 'string' ? m : 'Failed'); } finally { setSubmitting(false); }
  };

  const handleIssue = async (id: string) => {
    if (!confirm('Issue this invoice? This will deduct stock.')) return;
    try { await salesApi.issueInvoice(id); fetchInvoices(); }
    catch (err: unknown) { const m = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail; alert(typeof m === 'string' ? m : 'Issue failed'); }
  };

  const handleDownloadPDF = async (inv: SalesInvoice) => {
    try {
      toast.info('Generating PDF...');
      const response = await salesApi.downloadInvoicePdf(inv.id);
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `Invoice-${inv.invoice_number}.pdf`);
      document.body.appendChild(link);
      link.click();
      window.URL.revokeObjectURL(url);
      link.remove();
      toast.success('PDF downloaded successfully');
    } catch {
      toast.error('Failed to download PDF');
    }
  };

  const handleSearchSO = async () => {
    if (!soNumberSearch) return;
    setIsSearchingSO(true); setError('');
    try {
      const { data } = await salesApi.searchSalesOrderByNumber(soNumberSearch);
      const so = data.sales_order;
      if (so.status !== 'delivered' && so.status !== 'closed') {
        setError(`Cannot invoice SO in '${so.status}' status. Only delivered or closed.`);
        return;
      }
      setCustomerId(so.customer_id);
      setSoId(so.id);
      setItems(data.items.map((i: any) => ({
        product_id: i.product_id,
        quantity: i.quantity,
        unit_price: i.unit_price,
        discount_percent: i.discount_percent,
        gst_rate: i.gst_rate,
      })));
      toast.success('Sales order fetched successfully');
    } catch {
      setError('Sales order not found or error fetching');
    } finally {
      setIsSearchingSO(false);
    }
  };

  const sc: Record<string, string> = { draft: 'bg-gray-100 text-gray-700', issued: 'bg-blue-100 text-blue-700', partial_paid: 'bg-amber-100 text-amber-700', paid: 'bg-green-100 text-green-700', cancelled: 'bg-red-100 text-red-700' };

  return (
    <AppLayout title="Sales Invoices">
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <select className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
            <option value="">All</option><option value="draft">Draft</option><option value="issued">Issued</option><option value="partial_paid">Partial Paid</option><option value="paid">Paid</option><option value="cancelled">Cancelled</option>
          </select>
          <button onClick={() => { resetForm(); setShowForm(true); }} className="rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-primary/20 hover:bg-primary/90">+ New Invoice</button>
        </div>

        <div className="hms-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-neutral-200 bg-neutral-50">
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Invoice #</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Customer</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Date</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Due Date</th>
                <th className="px-4 py-3 text-right font-semibold text-neutral-600">Amount</th>
                <th className="px-4 py-3 text-right font-semibold text-neutral-600">Due</th>
                <th className="px-4 py-3 text-center font-semibold text-neutral-600">Status</th>
                <th className="px-4 py-3 text-center font-semibold text-neutral-600">Actions</th>
              </tr></thead>
              <tbody>
                {loading ? <tr><td colSpan={8} className="px-4 py-8 text-center text-neutral-500">Loading...</td></tr>
                : invoices.length === 0 ? <tr><td colSpan={8} className="px-4 py-8 text-center text-neutral-500">No invoices</td></tr>
                : invoices.map(inv => (
                  <tr key={inv.id} className="border-b border-neutral-100 hover:bg-neutral-50">
                    <td className="px-4 py-3 font-medium">{inv.invoice_number}</td>
                    <td className="px-4 py-3">{customers.find(c => c.id === inv.customer_id)?.company_name || '-'}</td>
                    <td className="px-4 py-3">{inv.invoice_date}</td>
                    <td className="px-4 py-3">{inv.due_date || '-'}</td>
                    <td className="px-4 py-3 text-right font-medium">{formatAmount(inv.total_amount)}</td>
                    <td className="px-4 py-3 text-right font-medium text-red-600">{inv.amount_due > 0 ? formatAmount(inv.amount_due) : '-'}</td>
                    <td className="px-4 py-3 text-center"><span className={`inline-block rounded-full px-2.5 py-1 text-xs font-semibold ${sc[inv.status] || 'bg-gray-100'}`}>{inv.status.replace('_', ' ')}</span></td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex items-center justify-center gap-2">
                        {inv.status === 'draft' && <button onClick={() => handleIssue(inv.id)} className="rounded px-2 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50">Issue</button>}
                        <button onClick={() => handleDownloadPDF(inv)} className="rounded px-2 py-1 text-xs font-medium text-neutral-600 hover:bg-neutral-100" title="Download PDF">
                          📄 PDF
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!loading && <p className="border-t border-neutral-200 px-4 py-3 text-xs text-neutral-500">Total: {invoices.length}</p>}
        </div>

        {showForm && (
          <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4 backdrop-blur-sm">
            <div className="hms-card my-8 w-full max-w-4xl space-y-6 p-6">
              <h2 className="font-display text-xl font-bold">{editingId ? 'Modify/Change' : 'New'} Invoice</h2>
              {error && <div className="rounded-lg bg-red-50 p-3 text-sm text-red-600">{error}</div>}
              
              {!editingId && (
                <div className="flex items-end gap-2 p-4 bg-neutral-50 rounded-lg border border-neutral-200">
                  <div className="flex-1">
                    <label className="mb-1 block text-sm font-semibold text-neutral-700">Auto-fill from SO #</label>
                    <input type="text" className="w-full hms-input" placeholder="e.g. SO-00001" value={soNumberSearch} onChange={e => setSoNumberSearch(e.target.value.toUpperCase())} />
                  </div>
                  <button type="button" onClick={handleSearchSO} disabled={isSearchingSO || !soNumberSearch} className="rounded-lg border border-neutral-300 bg-white px-4 py-2 text-sm font-semibold text-neutral-700 hover:bg-neutral-50 disabled:opacity-50">
                    {isSearchingSO ? 'Fetching...' : 'Fetch SO'}
                  </button>
                </div>
              )}

              <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Customer *</label><select className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={customerId} onChange={e => setCustomerId(e.target.value)}><option value="">Select</option>{customers.map(c => <option key={c.id} value={c.id}>{c.company_name}</option>)}</select></div>
                <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Invoice Date *</label><input type="date" className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={invoiceDate} onChange={e => setInvoiceDate(e.target.value)} /></div>
                <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Due Date</label><input type="date" className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={dueDate} onChange={e => setDueDate(e.target.value)} /></div>
              </div>
              <div>
                <div className="mb-2 flex items-center justify-between"><h3 className="text-sm font-semibold">Items</h3><button onClick={addItem} className="rounded bg-primary/10 px-3 py-1.5 text-xs font-semibold text-primary">+ Add</button></div>
                <div className="overflow-x-auto rounded-lg border border-neutral-200"><table className="w-full text-sm"><thead><tr className="bg-neutral-50"><th className="px-3 py-2 text-left">Product</th><th className="px-3 py-2 text-right w-20">Qty</th><th className="px-3 py-2 text-right w-28">Price (₹)</th><th className="px-3 py-2 text-right w-20">Disc %</th><th className="px-3 py-2 text-right w-20">GST</th><th className="px-3 py-2 text-right w-28">Total</th><th className="w-10"></th></tr></thead><tbody>
                  {items.map((item, idx) => (<tr key={idx} className="border-t border-neutral-100"><td className="px-3 py-2"><select className="w-full rounded border px-2 py-1.5 text-sm" value={item.product_id} onChange={e => updateItem(idx, 'product_id', e.target.value)}><option value="">Select</option>{products.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select></td><td className="px-3 py-2"><input type="number" min="0.01" step="0.01" className="w-full rounded border px-2 py-1.5 text-right text-sm" value={item.quantity} onChange={e => updateItem(idx, 'quantity', parseFloat(e.target.value)||0)} /></td><td className="px-3 py-2"><input type="number" min="0" className="w-full rounded border px-2 py-1.5 text-right text-sm" value={item.unit_price} onChange={e => updateItem(idx, 'unit_price', parseInt(e.target.value)||0)} /></td><td className="px-3 py-2"><input type="number" min="0" max="100" className="w-full rounded border px-2 py-1.5 text-right text-sm" value={item.discount_percent||0} onChange={e => updateItem(idx, 'discount_percent', parseFloat(e.target.value)||0)} /></td><td className="px-3 py-2"><select className="w-full rounded border px-2 py-1.5 text-sm" value={item.gst_rate} onChange={e => updateItem(idx, 'gst_rate', parseInt(e.target.value))}><option value={0}>0%</option><option value={5}>5%</option><option value={12}>12%</option><option value={18}>18%</option><option value={28}>28%</option></select></td><td className="px-3 py-2 text-right font-medium">{formatAmount(calcTotal(item))}</td><td className="px-3 py-2"><button onClick={() => removeItem(idx)} className="text-red-500">✕</button></td></tr>))}
                  {items.length === 0 && <tr><td colSpan={7} className="px-3 py-4 text-center text-neutral-400">No items</td></tr>}
                </tbody>{items.length > 0 && <tfoot><tr className="border-t-2 bg-neutral-50"><td colSpan={5} className="px-3 py-2 text-right font-semibold">Total:</td><td className="px-3 py-2 text-right font-bold text-primary">{formatAmount(items.reduce((s, i) => s + calcTotal(i), 0))}</td><td></td></tr></tfoot>}</table></div>
              </div>
              <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Notes</label><textarea className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" rows={2} value={notes} onChange={e => setNotes(e.target.value)} /></div>
              <div className="flex justify-end gap-3">
                <button onClick={() => { setShowForm(false); resetForm(); }} className="rounded-lg border border-neutral-200 bg-white px-4 py-2.5 text-sm font-semibold text-neutral-600">Cancel</button>
                <button onClick={handleSubmit} disabled={submitting} className="rounded-lg bg-primary px-6 py-2.5 text-sm font-semibold text-white shadow-lg shadow-primary/20 disabled:opacity-50">{submitting ? 'Saving...' : editingId ? 'Update' : 'Create Invoice'}</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
};

export default InvoicesPage;
