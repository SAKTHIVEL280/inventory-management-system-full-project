/**
 * GRN (Goods Receipt Notes) Page
 * List, create, confirm GRNs. Confirms add stock to ledger.
 */
import { useState, useEffect } from 'react';
import { AppLayout } from '../components/AppLayout';
import { purchaseApi, type GoodsReceiptNote, type CreateGRNPayload, type PurchaseLineItem } from '../api/purchase';
import { apiClient } from '../api/client';

interface ProductOption { id: string; name: string; product_code: string; purchase_price: number; gst_rate: number; }
interface SupplierOption { id: string; company_name: string; supplier_code: string; }

const GRNPage = () => {
  const [grns, setGRNs] = useState<GoodsReceiptNote[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [statusFilter, setStatusFilter] = useState('');
  const [suppliers, setSuppliers] = useState<SupplierOption[]>([]);
  const [products, setProducts] = useState<ProductOption[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const [supplierId, setSupplierId] = useState('');
  const [receiptDate, setReceiptDate] = useState(new Date().toISOString().split('T')[0]);
  const [supplierInvoiceNumber, setSupplierInvoiceNumber] = useState('');
  const [supplierInvoiceDate, setSupplierInvoiceDate] = useState('');
  const [notes, setNotes] = useState('');
  const [items, setItems] = useState<PurchaseLineItem[]>([]);

  const fetchGRNs = async () => {
    try { setLoading(true); const res = await purchaseApi.listGRNs(statusFilter || undefined); setGRNs(res.data.items || []); } catch { setError('Failed'); } finally { setLoading(false); }
  };
  const fetchMaster = async () => {
    try { const [s, p] = await Promise.all([apiClient.get('/api/v1/suppliers', { params: { page_size: 200 } }), apiClient.get('/api/v1/products', { params: { page_size: 200 } })]); setSuppliers(s.data.items || []); setProducts(p.data.items || []); } catch { /* */ }
  };

  useEffect(() => { fetchGRNs(); }, [statusFilter]);
  useEffect(() => { fetchMaster(); }, []);

  const resetForm = () => { setSupplierId(''); setReceiptDate(new Date().toISOString().split('T')[0]); setSupplierInvoiceNumber(''); setSupplierInvoiceDate(''); setNotes(''); setItems([]); setError(''); };
  const addItem = () => { setItems([...items, { product_id: '', quantity: 1, unit_price: 0, discount_percent: 0, gst_rate: 18 }]); };
  const updateItem = (idx: number, field: keyof PurchaseLineItem, value: string | number) => {
    const updated = [...items]; (updated[idx] as unknown as Record<string, unknown>)[field] = value;
    if (field === 'product_id') { const p = products.find(x => x.id === value); if (p) { updated[idx].unit_price = p.purchase_price; updated[idx].gst_rate = p.gst_rate; } }
    setItems(updated);
  };
  const removeItem = (idx: number) => setItems(items.filter((_, i) => i !== idx));
  const calcTotal = (i: PurchaseLineItem) => { const g = i.unit_price * i.quantity; const d = g * (i.discount_percent || 0) / 100; const t = g - d; return t + t * i.gst_rate / 100; };
  const formatAmount = (p: number) => `₹${(p / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;

  const handleSubmit = async () => {
    if (!supplierId || items.length === 0) { setError('Select supplier & add items'); return; }
    setSubmitting(true); setError('');
    try {
      const payload: CreateGRNPayload = {
        supplier_id: supplierId, receipt_date: receiptDate,
        supplier_invoice_number: supplierInvoiceNumber || undefined,
        supplier_invoice_date: supplierInvoiceDate || undefined,
        notes: notes || undefined,
        items: items.map(i => ({ product_id: i.product_id, quantity: Number(i.quantity), unit_price: Number(i.unit_price), discount_percent: Number(i.discount_percent || 0), gst_rate: Number(i.gst_rate) })),
      };
      await purchaseApi.createGRN(payload);
      setShowForm(false); resetForm(); fetchGRNs();
    } catch (err: unknown) { const m = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail; setError(typeof m === 'string' ? m : 'Failed'); } finally { setSubmitting(false); }
  };

  const handleConfirm = async (id: string) => {
    if (!confirm('Confirm this GRN? Stock will be added to inventory.')) return;
    try { await purchaseApi.confirmGRN(id); fetchGRNs(); }
    catch (err: unknown) { const m = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail; alert(typeof m === 'string' ? m : 'Failed'); }
  };
  const handleCancel = async (id: string) => {
    if (!confirm('Cancel this GRN?')) return;
    try { await purchaseApi.cancelGRN(id); fetchGRNs(); } catch { alert('Failed'); }
  };

  const sc: Record<string, string> = { draft: 'bg-gray-100 text-gray-700', confirmed: 'bg-green-100 text-green-700', cancelled: 'bg-red-100 text-red-700' };

  return (
    <AppLayout title="Goods Receipt Notes (GRN)">
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <select className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
            <option value="">All</option><option value="draft">Draft</option><option value="confirmed">Confirmed</option><option value="cancelled">Cancelled</option>
          </select>
          <button onClick={() => { resetForm(); setShowForm(true); }} className="rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-primary/20 hover:bg-primary/90">+ New GRN</button>
        </div>

        <div className="hms-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-neutral-200 bg-neutral-50">
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">GRN #</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Supplier</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Receipt Date</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Supplier Inv #</th>
                <th className="px-4 py-3 text-right font-semibold text-neutral-600">Amount</th>
                <th className="px-4 py-3 text-center font-semibold text-neutral-600">Status</th>
                <th className="px-4 py-3 text-center font-semibold text-neutral-600">Actions</th>
              </tr></thead>
              <tbody>
                {loading ? <tr><td colSpan={7} className="px-4 py-8 text-center text-neutral-500">Loading...</td></tr>
                : grns.length === 0 ? <tr><td colSpan={7} className="px-4 py-8 text-center text-neutral-500">No GRNs found</td></tr>
                : grns.map(g => (
                  <tr key={g.id} className="border-b border-neutral-100 hover:bg-neutral-50">
                    <td className="px-4 py-3 font-medium">{g.grn_number}</td>
                    <td className="px-4 py-3">{suppliers.find(s => s.id === g.supplier_id)?.company_name || '-'}</td>
                    <td className="px-4 py-3">{g.receipt_date}</td>
                    <td className="px-4 py-3">{g.supplier_invoice_number || '-'}</td>
                    <td className="px-4 py-3 text-right font-medium">{formatAmount(g.total_amount)}</td>
                    <td className="px-4 py-3 text-center"><span className={`inline-block rounded-full px-2.5 py-1 text-xs font-semibold ${sc[g.status] || 'bg-gray-100'}`}>{g.status}</span></td>
                    <td className="px-4 py-3 text-center">
                      {g.status === 'draft' && (
                        <div className="flex items-center justify-center gap-1">
                          <button onClick={() => handleConfirm(g.id)} className="rounded px-2 py-1 text-xs font-medium text-green-600 hover:bg-green-50">Confirm</button>
                          <button onClick={() => handleCancel(g.id)} className="rounded px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50">Cancel</button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!loading && <p className="border-t border-neutral-200 px-4 py-3 text-xs text-neutral-500">Total: {grns.length}</p>}
        </div>

        {showForm && (
          <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4 backdrop-blur-sm">
            <div className="hms-card my-8 w-full max-w-4xl space-y-6 p-6">
              <h2 className="font-display text-xl font-bold">New GRN (Goods Receipt)</h2>
              {error && <div className="rounded-lg bg-red-50 p-3 text-sm text-red-600">{error}</div>}
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
                <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Supplier *</label><select className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={supplierId} onChange={e => setSupplierId(e.target.value)}><option value="">Select</option>{suppliers.map(s => <option key={s.id} value={s.id}>{s.company_name}</option>)}</select></div>
                <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Receipt Date *</label><input type="date" className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={receiptDate} onChange={e => setReceiptDate(e.target.value)} /></div>
                <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Supplier Invoice #</label><input type="text" className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={supplierInvoiceNumber} onChange={e => setSupplierInvoiceNumber(e.target.value)} /></div>
                <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Supplier Invoice Date</label><input type="date" className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={supplierInvoiceDate} onChange={e => setSupplierInvoiceDate(e.target.value)} /></div>
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
                <button onClick={handleSubmit} disabled={submitting} className="rounded-lg bg-primary px-6 py-2.5 text-sm font-semibold text-white shadow-lg shadow-primary/20 disabled:opacity-50">{submitting ? 'Saving...' : 'Create GRN'}</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
};

export default GRNPage;
