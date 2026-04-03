/**
 * Sales Invoices Page
 * List, create, edit, issue invoices. GST-aware line items.
 */
import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { AppLayout } from '../components/AppLayout';
import { salesApi, type SalesInvoice, type CreateInvoicePayload, type SalesLineItem, type SalesOrder, type SalesInvoiceItem } from '../api/sales';
import { apiClient } from '../api/client';
import { toast } from 'sonner';
import { confirmWithToast } from '../utils/toastHelper';

interface ProductOption { id: string; name: string; product_code: string; selling_price: number; mrp: number; gst_rate: number; hsn_code: string; description?: string; }
interface CustomerOption { id: string; company_name: string; customer_code: string; payment_terms_days?: number; }

const InvoicesPage = () => {
  const [invoices, setInvoices] = useState<SalesInvoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [customers, setCustomers] = useState<CustomerOption[]>([]);
  const [products, setProducts] = useState<ProductOption[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [selectedInvoice, setSelectedInvoice] = useState<SalesInvoice | null>(null);
  const [selectedInvoiceItems, setSelectedInvoiceItems] = useState<SalesInvoiceItem[]>([]);
  const [showInvoiceDetail, setShowInvoiceDetail] = useState(false);
  const [salesOrders, setSalesOrders] = useState<SalesOrder[]>([]);
  const [loadingSOs, setLoadingSOs] = useState(false);
  const [showSoDropdown, setShowSoDropdown] = useState(false);

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

  const fetchSalesOrdersForInvoice = async () => {
    try {
      setLoadingSOs(true);
      const res = await salesApi.listSalesOrders(undefined, 1, 500);
      setSalesOrders(res.data.items || []);
    } catch {
      setSalesOrders([]);
    } finally {
      setLoadingSOs(false);
    }
  };

  useEffect(() => { fetchInvoices(); }, [statusFilter]);
  useEffect(() => { fetchMasterData(); }, []);
  useEffect(() => {
    if (showForm && !editingId && salesOrders.length === 0) {
      fetchSalesOrdersForInvoice();
    }
  }, [showForm, editingId, salesOrders.length]);

  const resetForm = () => { setCustomerId(''); setInvoiceDate(new Date().toISOString().split('T')[0]); setDueDate(''); setNotes(''); setItems([]); setEditingId(null); setError(''); setSoNumberSearch(''); setSoId(undefined); };
  const addItem = () => {
    setItems([
      ...items,
      {
        product_id: '',
        order_unit: '',
        batch_no: '',
        manufacture_date: '',
        expiry_date: '',
        quantity: 1,
        free_quantity: 0,
        unit_price: 0,
        discount_percent: 0,
        gst_rate: 18,
      },
    ]);
  };
  const paiseToRupees = (paise: number) => (Number.isFinite(paise) ? paise / 100 : 0);
  const rupeesToPaise = (value: string | number) => {
    const num = typeof value === 'number' ? value : parseFloat(value);
    return Number.isFinite(num) ? Math.round(num * 100) : 0;
  };

  // SAL-025: Auto-calculate due date from customer payment terms when customer changes
  const handleCustomerChange = (newCustomerId: string) => {
    setCustomerId(newCustomerId);
    if (newCustomerId) {
      const cust = customers.find(c => c.id === newCustomerId);
      if (cust?.payment_terms_days && invoiceDate) {
        const baseDate = new Date(invoiceDate);
        baseDate.setDate(baseDate.getDate() + cust.payment_terms_days);
        setDueDate(baseDate.toISOString().split('T')[0]);
      }
    }
  };

  const updateItem = (idx: number, field: keyof SalesLineItem, value: string | number) => {
    const updated = [...items]; (updated[idx] as unknown as Record<string, unknown>)[field] = value;
    // SAL-020/022/023: Auto-fill MRP and GST from product master
    if (field === 'product_id') { const p = products.find(x => x.id === value); if (p) { updated[idx].unit_price = p.mrp || p.selling_price; updated[idx].gst_rate = p.gst_rate; } }
    setItems(updated);
  };
  const removeItem = (idx: number) => { setItems(items.filter((_, i) => i !== idx)); };
  const calcTotal = (i: SalesLineItem) => { const g = i.unit_price * i.quantity; const d = g * (i.discount_percent || 0) / 100; const t = g - d; return Math.round(t + t * i.gst_rate / 100); };
  const formatAmount = (p: number) => `₹${(p / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
  // SAL-028: Proper status label formatting with correct capitalization
  const formatStatusLabel = (status?: string) => {
    const s = (status || 'unknown').replace('_', ' ');
    return s.charAt(0).toUpperCase() + s.slice(1);
  };
  const productById = (id: string) => products.find(p => p.id === id);

  const handleSubmit = async () => {
    if (!customerId || items.length === 0) { setError('Select customer & add items'); return; }
    setSubmitting(true); setError('');
    try {
      const payload: CreateInvoicePayload = {
        customer_id: customerId, sales_order_id: undefined, invoice_date: invoiceDate, due_date: dueDate || undefined,
        bill_to_customer_id: customerId, notes: notes || undefined,
        items: items.map(i => ({
          product_id: i.product_id,
          order_unit: i.order_unit || undefined,
          batch_no: i.batch_no || undefined,
          manufacture_date: i.manufacture_date || undefined,
          expiry_date: i.expiry_date || undefined,
          quantity: Number(i.quantity),
          free_quantity: Number(i.free_quantity || 0),
          unit_price: Number(i.unit_price),
          discount_percent: Number(i.discount_percent || 0),
          gst_rate: Number(i.gst_rate),
        })),
      };
      if (editingId) await salesApi.updateInvoice(editingId, payload); else await salesApi.createInvoice(payload);
      setShowForm(false); resetForm(); fetchInvoices();
    } catch (err: unknown) { const m = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail; setError(typeof m === 'string' ? m : 'Failed'); } finally { setSubmitting(false); }
  };

  const handleIssue = async (id: string) => {
    const confirmed = await confirmWithToast('Issue this invoice? This will deduct stock.', {
      type: 'warning',
    });
    if (!confirmed) return;
    try { await salesApi.issueInvoice(id); fetchInvoices(); }
    catch (err: unknown) {
      const m = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(typeof m === 'string' ? m : 'Issue failed');
    }
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

  const handleViewInvoice = async (inv: SalesInvoice) => {
    try {
      const { data } = await salesApi.getInvoice(inv.id);
      setSelectedInvoice(data.invoice || inv);
      setSelectedInvoiceItems(data.items || []);
      setShowInvoiceDetail(true);
    } catch {
      setSelectedInvoice(inv);
      setSelectedInvoiceItems([]);
      setShowInvoiceDetail(true);
    }
  };

  const handleSelectSO = async (so: SalesOrder) => {
    setIsSearchingSO(true); setError('');
    try {
      const { data } = await salesApi.getSalesOrder(so.id);
      const selectedSO = data.sales_order;
      if (selectedSO.status !== 'confirmed' && selectedSO.status !== 'fulfilled' && selectedSO.status !== 'partial') {
        setError(`Cannot invoice SO in '${selectedSO.status}' status. Only confirmed, partial, or fulfilled.`);
        return;
      }
      setCustomerId(selectedSO.customer_id);
      setSoId(selectedSO.id);
      setSoNumberSearch(selectedSO.so_number);
      setShowSoDropdown(false);
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

  const customerNameById = (customerId: string) => {
    return customers.find((c) => c.id === customerId)?.company_name || 'Unknown customer';
  };
  const productNameById = (productId: string) => {
    return products.find((p) => p.id === productId)?.name || productId;
  };

  const filteredInvoices = invoices.filter((inv) => {
    const q = searchQuery.trim().toLowerCase();
    const customerName = customerNameById(inv.customer_id).toLowerCase();
    const matchesSearch =
      !q ||
      inv.invoice_number.toLowerCase().includes(q) ||
      customerName.includes(q) ||
      inv.status.toLowerCase().includes(q) ||
      inv.invoice_date.toLowerCase().includes(q) ||
      (inv.due_date || '').toLowerCase().includes(q);
    const matchesFrom = !dateFrom || inv.invoice_date >= dateFrom;
    const matchesTo = !dateTo || inv.invoice_date <= dateTo;
    return matchesSearch && matchesFrom && matchesTo;
  });

  const soQuery = soNumberSearch.trim().toLowerCase();
  const soSuggestions = soQuery
    ? salesOrders
        .filter((so) => so.status === 'confirmed' || so.status === 'partial' || so.status === 'fulfilled')
        .filter((so) => {
          const haystack = [
            so.so_number,
            customerNameById(so.customer_id),
            so.order_date || '',
            so.expected_delivery_date || '',
            so.status,
            String((so.total_amount / 100).toFixed(2)),
          ]
            .join(' ')
            .toLowerCase();
          return haystack.includes(soQuery);
        })
        .slice(0, 12)
    : [];

  const sc: Record<string, string> = { draft: 'bg-gray-100 text-gray-700', issued: 'bg-blue-100 text-blue-700', partial_paid: 'bg-amber-100 text-amber-700', paid: 'bg-green-100 text-green-700', cancelled: 'bg-red-100 text-red-700' };

  return (
    <AppLayout title="Sales Invoices">
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <select className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
              <option value="">All</option><option value="draft">Draft</option><option value="issued">Issued</option><option value="partial_paid">Partial Paid</option><option value="paid">Paid</option><option value="cancelled">Cancelled</option>
            </select>
            <input
              type="text"
              className="w-64 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm"
              placeholder="Search invoice #, customer, status..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <div className="inline-flex items-center gap-2 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm">
              <span className="text-xs font-semibold uppercase tracking-wide text-neutral-500">From</span>
              <input
                type="date"
                className="bg-transparent text-sm outline-none"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                title="Invoice date from"
              />
            </div>
            <div className="inline-flex items-center gap-2 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm">
              <span className="text-xs font-semibold uppercase tracking-wide text-neutral-500">To</span>
              <input
                type="date"
                className="bg-transparent text-sm outline-none"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                title="Invoice date to"
              />
            </div>
          </div>
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
                : filteredInvoices.length === 0 ? <tr><td colSpan={8} className="px-4 py-8 text-center text-neutral-500">No invoices</td></tr>
                : filteredInvoices.map(inv => (
                  <tr key={inv.id} className="border-b border-neutral-100 hover:bg-neutral-50">
                    <td className="px-4 py-3 font-medium">{inv.invoice_number}</td>
                    <td className="px-4 py-3">{customerNameById(inv.customer_id)}</td>
                    <td className="px-4 py-3">{inv.invoice_date}</td>
                    <td className="px-4 py-3">{inv.due_date || '-'}</td>
                    <td className="px-4 py-3 text-right font-medium">{formatAmount(inv.total_amount)}</td>
                    <td className="px-4 py-3 text-right font-medium text-red-600">{inv.amount_due > 0 ? formatAmount(inv.amount_due) : '-'}</td>
                    <td className="px-4 py-3 text-center"><span className={`inline-block rounded-full px-2.5 py-1 text-xs font-semibold ${sc[inv.status] || 'bg-gray-100'}`}>{formatStatusLabel(inv.status)}</span></td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex items-center justify-center gap-2">
                        <button onClick={() => handleViewInvoice(inv)} className="rounded px-2 py-1 text-xs font-medium text-primary hover:bg-primary/10">View</button>
                        {inv.status === 'draft' && <button onClick={() => handleIssue(inv.id)} className="rounded px-2 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50">Issue</button>}
                        <button
                          onClick={() => handleDownloadPDF(inv)}
                          className="inline-flex items-center gap-1 rounded border border-neutral-200 bg-white px-2.5 py-1 text-xs font-semibold text-neutral-700 hover:bg-neutral-50"
                          title="Download PDF"
                        >
                          <span className="material-icons text-sm" aria-hidden="true">picture_as_pdf</span>
                          Download PDF
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!loading && <p className="border-t border-neutral-200 px-4 py-3 text-xs text-neutral-500">Showing {filteredInvoices.length} of {invoices.length}</p>}
        </div>

        {showForm && createPortal(
          <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-2 sm:p-4 backdrop-blur-sm">
            <div className="hms-card my-4 sm:my-8 w-[min(96vw,1500px)] max-w-none space-y-6 p-4 sm:p-6">
              <h2 className="font-display text-xl font-bold">{editingId ? 'Modify/Change' : 'New'} Invoice</h2>
              {error && <div className="rounded-lg bg-red-50 p-3 text-sm text-red-600">{error}</div>}
              
              {!editingId && (
                <div className="rounded-lg border border-neutral-200 bg-neutral-50 p-4 text-sm text-neutral-600">
                  Invoice creation is independent of Sales Order auto-fill.
                </div>
              )}

              <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                {/* SAL-025: Customer select triggers due date auto-calc */}
                <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Customer *</label><select className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={customerId} onChange={e => handleCustomerChange(e.target.value)}><option value="">Select</option>{customers.map(c => <option key={c.id} value={c.id}>{c.company_name} ({c.customer_code})</option>)}</select></div>
                <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Invoice Date *</label><input type="date" className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={invoiceDate} onChange={e => setInvoiceDate(e.target.value)} /></div>
                {/* SAL-025/026: Due Date auto-calculated from Customer Payment Terms, allows manual override */}
                <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Due Date <span className="text-xs text-neutral-400">(auto from payment terms)</span></label><input type="date" className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={dueDate} onChange={e => setDueDate(e.target.value)} /></div>
              </div>
              <div>
                <div className="mb-2 flex items-center justify-between"><h3 className="text-sm font-semibold">Items</h3><button onClick={addItem} className="rounded bg-primary/10 px-3 py-1.5 text-xs font-semibold text-primary">+ Add</button></div>
                <div className="overflow-x-auto rounded-lg border border-neutral-200">
                  <table className="w-full min-w-[1600px] table-fixed text-sm">
                    <thead>
                      <tr className="bg-neutral-50">
                        <th className="w-[18%] px-3 py-2 text-left">Product</th>
                        <th className="w-[8%] px-3 py-2 text-left">Product ID</th>
                        <th className="w-[10%] px-3 py-2 text-left">Description</th>
                        <th className="w-[8%] px-3 py-2 text-left">Order Unit</th>
                        <th className="w-[8%] px-3 py-2 text-left">Batch</th>
                        <th className="w-[8%] px-3 py-2 text-left">MFG Date</th>
                        <th className="w-[8%] px-3 py-2 text-left">EXP Date</th>
                        <th className="w-[7%] px-3 py-2 text-left">HSN</th>
                        <th className="w-16 px-3 py-2 text-right">Qty</th>
                        <th className="w-16 px-3 py-2 text-right">Free</th>
                        <th className="w-28 px-3 py-2 text-right">MRP (₹)</th>
                        <th className="w-16 px-3 py-2 text-right">Disc %</th>
                        <th className="w-16 px-3 py-2 text-right">GST</th>
                        <th className="w-28 px-3 py-2 text-right">Total</th>
                        <th className="w-20 px-3 py-2 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((item, idx) => {
                        const prod = productById(item.product_id);
                        return (
                        <tr key={idx} className="border-t border-neutral-100">
                          <td className="px-3 py-2">
                            <select className="w-full rounded border px-2 py-1.5 text-sm" value={item.product_id} onChange={e => updateItem(idx, 'product_id', e.target.value)}>
                              <option value="">Select</option>
                              {products.map(p => <option key={p.id} value={p.id}>{p.name} ({p.product_code})</option>)}
                            </select>
                          </td>
                          {/* SAL-013: Product ID column */}
                          <td className="px-3 py-2 text-xs text-neutral-500 font-mono">{prod?.product_code || '-'}</td>
                          {/* SAL-014: Description column */}
                          <td className="px-3 py-2 text-xs text-neutral-500">{prod?.description || prod?.name || '-'}</td>
                          <td className="px-3 py-2">
                            <input type="text" className="w-full rounded border px-2 py-1.5 text-sm" value={item.order_unit || ''} onChange={e => updateItem(idx, 'order_unit', e.target.value)} placeholder="e.g. Box" />
                          </td>
                          <td className="px-3 py-2">
                            <input type="text" className="w-full rounded border px-2 py-1.5 text-sm" value={item.batch_no || ''} onChange={e => updateItem(idx, 'batch_no', e.target.value)} placeholder="Batch" />
                          </td>
                          <td className="px-3 py-2">
                            <input type="date" className="w-full rounded border px-2 py-1.5 text-sm" value={item.manufacture_date || ''} onChange={e => updateItem(idx, 'manufacture_date', e.target.value)} />
                          </td>
                          <td className="px-3 py-2">
                            <input type="date" className="w-full rounded border px-2 py-1.5 text-sm" value={item.expiry_date || ''} onChange={e => updateItem(idx, 'expiry_date', e.target.value)} />
                          </td>
                          {/* SAL-021: HSN Code column */}
                          <td className="px-3 py-2 text-xs text-neutral-500">{prod?.hsn_code || '-'}</td>
                          <td className="px-3 py-2">
                            <input type="number" min="0.01" step="0.01" className="w-full rounded border px-2 py-1.5 text-right text-sm" value={item.quantity} onChange={e => updateItem(idx, 'quantity', parseFloat(e.target.value) || 0)} />
                          </td>
                          <td className="px-3 py-2">
                            <input type="number" min="0" step="0.01" className="w-full rounded border px-2 py-1.5 text-right text-sm" value={item.free_quantity || 0} onChange={e => updateItem(idx, 'free_quantity', parseFloat(e.target.value) || 0)} />
                          </td>
                          {/* SAL-020: MRP auto-fills from Product Master */}
                          <td className="px-3 py-2">
                            <input type="number" min="0" step="0.01" className="w-full rounded border px-2 py-1.5 text-right text-sm" value={paiseToRupees(item.unit_price)} onChange={e => updateItem(idx, 'unit_price', rupeesToPaise(e.target.value))} />
                          </td>
                          <td className="px-3 py-2">
                            <input type="number" min="0" max="100" className="w-full rounded border px-2 py-1.5 text-right text-sm" value={item.discount_percent || 0} onChange={e => updateItem(idx, 'discount_percent', parseFloat(e.target.value) || 0)} />
                          </td>
                          {/* SAL-022/023: GST auto-fills from Product Master */}
                          <td className="px-3 py-2">
                            <select className="w-full rounded border px-2 py-1.5 text-sm" value={item.gst_rate} onChange={e => updateItem(idx, 'gst_rate', parseInt(e.target.value))}>
                              <option value={0}>0%</option>
                              <option value={5}>5%</option>
                              <option value={12}>12%</option>
                              <option value={18}>18%</option>
                              <option value={28}>28%</option>
                            </select>
                          </td>
                          <td className="px-3 py-2 text-right font-medium">{formatAmount(calcTotal(item))}</td>
                          <td className="px-3 py-2 text-right">
                            <button onClick={() => removeItem(idx)} className="inline-flex items-center gap-1 whitespace-nowrap text-red-500">
                              <span className="material-icons text-sm" aria-hidden="true">delete_outline</span>Remove
                            </button>
                          </td>
                        </tr>
                        );
                      })}
                  {items.length === 0 && <tr><td colSpan={15} className="px-3 py-4 text-center text-neutral-400">No items</td></tr>}
                    </tbody>
                    {items.length > 0 && (
                      <tfoot>
                        <tr className="border-t-2 bg-neutral-50">
                          <td colSpan={13} className="px-3 py-2 text-right font-semibold">Total:</td>
                          <td className="px-3 py-2 text-right font-bold text-primary">{formatAmount(items.reduce((s, i) => s + calcTotal(i), 0))}</td>
                          <td></td>
                        </tr>
                      </tfoot>
                    )}
                  </table>
                </div>
              </div>
              <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Notes</label><textarea className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" rows={2} value={notes} onChange={e => setNotes(e.target.value)} /></div>
              <div className="flex justify-end gap-3">
                <button onClick={() => { setShowForm(false); resetForm(); }} className="rounded-lg border border-neutral-200 bg-white px-4 py-2.5 text-sm font-semibold text-neutral-600">Cancel</button>
                <button onClick={handleSubmit} disabled={submitting} className="rounded-lg bg-primary px-6 py-2.5 text-sm font-semibold text-white shadow-lg shadow-primary/20 disabled:opacity-50">{submitting ? 'Saving...' : editingId ? 'Update' : 'Create Invoice'}</button>
              </div>
            </div>
          </div>,
          document.body
        )}

        {showInvoiceDetail && selectedInvoice && createPortal(
          <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4 backdrop-blur-sm" onClick={() => setShowInvoiceDetail(false)}>
            <div className="hms-card my-8 w-full max-w-3xl space-y-6 p-6" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="font-display text-xl font-bold">Invoice: {selectedInvoice.invoice_number}</h2>
                  <p className="mt-1 text-sm text-neutral-600">Customer: {customers.find(c => c.id === selectedInvoice.customer_id)?.company_name || '-'}</p>
                </div>
                <div className="flex items-center gap-2">
                  {/* SAL-027: Edit button in Invoice View for draft invoices */}
                  {selectedInvoice.status === 'draft' && (
                    <button
                      onClick={() => {
                        setShowInvoiceDetail(false);
                        // Load into edit form
                        setEditingId(selectedInvoice.id);
                        setCustomerId(selectedInvoice.customer_id);
                        setInvoiceDate(selectedInvoice.invoice_date);
                        setDueDate(selectedInvoice.due_date || '');
                        setNotes(selectedInvoice.notes || '');
                        setItems(selectedInvoiceItems.map(i => ({
                          product_id: i.product_id,
                          order_unit: (i as any).order_unit || '',
                          batch_no: (i as any).batch_no || '',
                          manufacture_date: (i as any).manufacture_date || '',
                          expiry_date: (i as any).expiry_date || '',
                          quantity: i.quantity,
                          free_quantity: (i as any).free_quantity || 0,
                          unit_price: i.unit_price,
                          discount_percent: i.discount_percent || 0,
                          gst_rate: i.gst_rate,
                        })));
                        setShowForm(true);
                      }}
                      className="inline-flex items-center gap-1 rounded-lg border border-primary bg-primary/5 px-3 py-2 text-xs font-semibold text-primary hover:bg-primary/10"
                    >
                      <span className="material-icons text-sm" aria-hidden="true">edit</span>
                      Edit Invoice
                    </button>
                  )}
                  <button
                    onClick={() => handleDownloadPDF(selectedInvoice)}
                    className="inline-flex items-center gap-1 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs font-semibold text-neutral-700 hover:bg-neutral-50"
                  >
                    <span className="material-icons text-sm" aria-hidden="true">picture_as_pdf</span>
                    Download PDF
                  </button>
                  <button onClick={() => setShowInvoiceDetail(false)} className="text-2xl text-neutral-400 hover:text-neutral-600">&times;</button>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 rounded-lg bg-neutral-50 p-4 md:grid-cols-4">
                <div>
                  <p className="text-xs text-neutral-600">Invoice Date</p>
                  <p className="font-medium">{selectedInvoice.invoice_date}</p>
                </div>
                <div>
                  <p className="text-xs text-neutral-600">Due Date</p>
                  <p className="font-medium">{selectedInvoice.due_date || '-'}</p>
                </div>
                <div>
                  <p className="text-xs text-neutral-600">Status</p>
                  <span className={`inline-block rounded-full px-2.5 py-1 text-xs font-semibold ${sc[selectedInvoice.status] || 'bg-gray-100'}`}>
                    {formatStatusLabel(selectedInvoice.status)}
                  </span>
                </div>
                <div>
                  <p className="text-xs text-neutral-600">Total</p>
                  <p className="font-semibold">{formatAmount(selectedInvoice.total_amount)}</p>
                </div>
              </div>

              <div className="grid grid-cols-1 gap-4 rounded-lg border border-neutral-200 p-4 md:grid-cols-3">
                <div>
                  <p className="text-xs text-neutral-600">Subtotal</p>
                  <p className="font-medium">{formatAmount(selectedInvoice.subtotal)}</p>
                </div>
                <div>
                  <p className="text-xs text-neutral-600">Amount Paid</p>
                  <p className="font-medium text-green-700">{formatAmount(selectedInvoice.amount_paid)}</p>
                </div>
                <div>
                  <p className="text-xs text-neutral-600">Amount Due</p>
                  <p className="font-medium text-red-600">{selectedInvoice.amount_due > 0 ? formatAmount(selectedInvoice.amount_due) : '-'}</p>
                </div>
              </div>

              {selectedInvoice.notes && (
                <div>
                  <p className="mb-1 text-xs text-neutral-600">Notes</p>
                  <p className="rounded-lg bg-neutral-50 p-3 text-sm text-neutral-700">{selectedInvoice.notes}</p>
                </div>
              )}

              {selectedInvoiceItems.length > 0 && (
                <div>
                  <p className="mb-2 text-sm font-semibold text-neutral-700">Items</p>
                  <div className="overflow-x-auto rounded-lg border border-neutral-200">
                    <table className="w-full min-w-[700px] text-sm">
                      <thead>
                        <tr className="bg-neutral-50">
                          <th className="px-3 py-2 text-left">Product</th>
                          <th className="px-3 py-2 text-right">Qty</th>
                          <th className="px-3 py-2 text-right">Unit Price</th>
                          <th className="px-3 py-2 text-right">Discount %</th>
                          <th className="px-3 py-2 text-right">GST %</th>
                          <th className="px-3 py-2 text-right">Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedInvoiceItems.map((item) => (
                          <tr key={item.id} className="border-t border-neutral-100">
                            <td className="px-3 py-2">{item.description || productNameById(item.product_id)}</td>
                            <td className="px-3 py-2 text-right">{item.quantity}</td>
                            <td className="px-3 py-2 text-right">{formatAmount(item.unit_price)}</td>
                            <td className="px-3 py-2 text-right">{item.discount_percent || 0}</td>
                            <td className="px-3 py-2 text-right">{item.gst_rate}</td>
                            <td className="px-3 py-2 text-right font-medium">{formatAmount(item.total_amount)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              <div className="flex justify-end">
                <button onClick={() => setShowInvoiceDetail(false)} className="rounded-lg border border-neutral-200 bg-white px-4 py-2 text-sm font-semibold hover:bg-neutral-50">
                  Close
                </button>
              </div>
            </div>
          </div>,
          document.body
        )}
      </div>
    </AppLayout>
  );
};

export default InvoicesPage;

