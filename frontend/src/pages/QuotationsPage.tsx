/**
 * Quotations Page
 * List, create, edit quotations. Send to customer, convert to Sales Order.
 */
import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { AppLayout } from '../components/AppLayout';
import { salesApi, type Quotation, type CreateQuotationPayload, type SalesLineItem } from '../api/sales';
import { apiClient } from '../api/client';

interface ProductOption {
  id: string;
  name: string;
  product_code: string;
  selling_price: number;
  gst_rate: number;
}

interface CustomerOption {
  id: string;
  company_name: string;
  customer_code: string;
}

const QuotationsPage = () => {
  const [quotations, setQuotations] = useState<Quotation[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState('');
  const [archiveView, setArchiveView] = useState<'active' | 'archived'>('active');
  const [searchQuery, setSearchQuery] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [customers, setCustomers] = useState<CustomerOption[]>([]);
  const [products, setProducts] = useState<ProductOption[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  // Form state
  const [customerId, setCustomerId] = useState('');
  const [quotationDate, setQuotationDate] = useState(new Date().toISOString().split('T')[0]);
  const [validUntil, setValidUntil] = useState('');
  const [notes, setNotes] = useState('');
  const [items, setItems] = useState<SalesLineItem[]>([]);

  const fetchQuotations = async () => {
    try {
      setLoading(true);
      const res = await salesApi.listQuotations(statusFilter || undefined, 1, 20, {
        archived_only: archiveView === 'archived',
      });
      setQuotations(res.data.items || []);
    } catch {
      setError('Failed to load quotations');
    } finally {
      setLoading(false);
    }
  };

  const fetchMasterData = async () => {
    try {
      const [custRes, prodRes] = await Promise.all([
        apiClient.get('/api/v1/customers', { params: { page_size: 100 } }),
        apiClient.get('/api/v1/products', { params: { page_size: 100 } }),
      ]);
      setCustomers(custRes.data.items || []);
      setProducts(prodRes.data.items || []);
    } catch {
      /* ignore */
    }
  };

  useEffect(() => { fetchQuotations(); }, [statusFilter, archiveView]);
  useEffect(() => { fetchMasterData(); }, []);

  const resetForm = () => {
    setCustomerId('');
    setQuotationDate(new Date().toISOString().split('T')[0]);
    setValidUntil('');
    setNotes('');
    setItems([]);
    setEditingId(null);
    setError('');
  };

  const addItem = () => {
    setItems([...items, { product_id: '', quantity: 1, unit_price: 0, discount_percent: 0, gst_rate: 18 }]);
  };

  const updateItem = (index: number, field: keyof SalesLineItem, value: string | number) => {
    const updated = [...items];
    (updated[index] as unknown as Record<string, unknown>)[field] = value;
    // Auto-fill price and GST when product selected
    if (field === 'product_id') {
      const product = products.find(p => p.id === value);
      if (product) {
        updated[index].unit_price = product.selling_price;
        updated[index].gst_rate = product.gst_rate;
      }
    }
    setItems(updated);
  };

  const removeItem = (index: number) => {
    setItems(items.filter((_, i) => i !== index));
  };

  const calcItemTotal = (item: SalesLineItem) => {
    const gross = item.unit_price * item.quantity;
    const discount = gross * (item.discount_percent || 0) / 100;
    const taxable = gross - discount;
    const gst = taxable * item.gst_rate / 100;
    return taxable + gst;
  };

  const handleSubmit = async () => {
    if (!customerId || items.length === 0) {
      setError('Please select a customer and add at least one item');
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      const payload: CreateQuotationPayload = {
        customer_id: customerId,
        quotation_date: quotationDate,
        valid_until: validUntil || undefined,
        notes: notes || undefined,
        status: 'draft',
        items: items.map(i => ({
          product_id: i.product_id,
          quantity: Number(i.quantity),
          unit_price: Number(i.unit_price),
          discount_percent: Number(i.discount_percent || 0),
          gst_rate: Number(i.gst_rate),
        })),
      };

      if (editingId) {
        await salesApi.updateQuotation(editingId, payload);
      } else {
        await salesApi.createQuotation(payload);
      }
      setShowForm(false);
      resetForm();
      fetchQuotations();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof msg === 'string' ? msg : 'Failed to save quotation');
    } finally {
      setSubmitting(false);
    }
  };

  const handleStatusChange = async (id: string, newStatus: string) => {
    try {
      await salesApi.updateQuotationStatus(id, newStatus);
      fetchQuotations();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      alert(typeof msg === 'string' ? msg : 'Status update failed');
    }
  };

  const handleConvertToSO = async (id: string) => {
    if (!confirm('Convert this quotation to a Sales Order?')) return;
    try {
      await salesApi.convertQuotationToSO(id);
      alert('Sales Order created successfully!');
      fetchQuotations();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      alert(typeof msg === 'string' ? msg : 'Conversion failed');
    }
  };

  const handleArchiveToggle = async (id: string, archived: boolean) => {
    try {
      if (archived) {
        await salesApi.restoreQuotation(id);
      } else {
        await salesApi.archiveQuotation(id);
      }
      fetchQuotations();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      alert(typeof msg === 'string' ? msg : archived ? 'Restore failed' : 'Archive failed');
    }
  };

  const statusColors: Record<string, string> = {
    draft: 'bg-gray-100 text-gray-700',
    sent: 'bg-blue-100 text-blue-700',
    accepted: 'bg-green-100 text-green-700',
    rejected: 'bg-red-100 text-red-700',
    expired: 'bg-amber-100 text-amber-700',
    converted: 'bg-purple-100 text-purple-700',
  };

  const formatAmount = (paise: number) => `₹${(paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;

  const customerNameById = (id: string) => customers.find((c) => c.id === id)?.company_name || '-';

  const filteredQuotations = quotations.filter((q) => {
    const term = searchQuery.trim().toLowerCase();
    const customerName = customerNameById(q.customer_id).toLowerCase();
    const matchesSearch =
      !term ||
      q.quotation_number.toLowerCase().includes(term) ||
      customerName.includes(term) ||
      q.status.toLowerCase().includes(term) ||
      q.quotation_date.toLowerCase().includes(term) ||
      (q.valid_until || '').toLowerCase().includes(term);
    const matchesFrom = !dateFrom || q.quotation_date >= dateFrom;
    const matchesTo = !dateTo || q.quotation_date <= dateTo;
    return matchesSearch && matchesFrom && matchesTo;
  });

  return (
    <AppLayout title="Quotations">
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <select
              className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm"
              value={statusFilter}
              onChange={e => setStatusFilter(e.target.value)}
            >
              <option value="">All Statuses</option>
              <option value="draft">Draft</option>
              <option value="sent">Sent</option>
              <option value="accepted">Accepted</option>
              <option value="rejected">Rejected</option>
              <option value="expired">Expired</option>
              <option value="converted">Converted</option>
            </select>
            <select
              className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm"
              value={archiveView}
              onChange={(e) => setArchiveView(e.target.value as 'active' | 'archived')}
            >
              <option value="active">Active Only</option>
              <option value="archived">Archived Only</option>
            </select>
            <input
              type="text"
              className="w-64 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm"
              placeholder="Search quotation #, customer, status..."
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
                title="Quotation date from"
              />
            </div>
            <div className="inline-flex items-center gap-2 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm">
              <span className="text-xs font-semibold uppercase tracking-wide text-neutral-500">To</span>
              <input
                type="date"
                className="bg-transparent text-sm outline-none"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                title="Quotation date to"
              />
            </div>
          </div>
          <button
            onClick={() => { resetForm(); setShowForm(true); }}
            className="rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-primary/20 transition hover:bg-primary/90"
          >
            + New Quotation
          </button>
        </div>

        {/* Table */}
        <div className="hms-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-neutral-200 bg-neutral-50">
                  <th className="px-4 py-3 text-left font-semibold text-neutral-600">Quotation #</th>
                  <th className="px-4 py-3 text-left font-semibold text-neutral-600">Customer</th>
                  <th className="px-4 py-3 text-left font-semibold text-neutral-600">Date</th>
                  <th className="px-4 py-3 text-left font-semibold text-neutral-600">Valid Until</th>
                  <th className="px-4 py-3 text-right font-semibold text-neutral-600">Amount</th>
                  <th className="px-4 py-3 text-center font-semibold text-neutral-600">Status</th>
                  <th className="px-4 py-3 text-center font-semibold text-neutral-600">Actions</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan={7} className="px-4 py-8 text-center text-neutral-500">Loading...</td></tr>
                ) : filteredQuotations.length === 0 ? (
                  <tr><td colSpan={7} className="px-4 py-8 text-center text-neutral-500">No quotations found</td></tr>
                ) : filteredQuotations.map(q => (
                  <tr key={q.id} className="border-b border-neutral-100 hover:bg-neutral-50">
                    <td className="px-4 py-3 font-medium">{q.quotation_number}</td>
                    <td className="px-4 py-3">{customerNameById(q.customer_id)}</td>
                    <td className="px-4 py-3">{q.quotation_date}</td>
                    <td className="px-4 py-3">{q.valid_until || '-'}</td>
                    <td className="px-4 py-3 text-right font-medium">{formatAmount(q.total_amount)}</td>
                    <td className="px-4 py-3 text-center">
                      <span className={`inline-block rounded-full px-2.5 py-1 text-xs font-semibold ${statusColors[q.status] || 'bg-gray-100'}`}>
                        {q.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex items-center justify-center gap-1">
                        {archiveView === 'active' && q.status === 'draft' && (
                          <button onClick={() => handleStatusChange(q.id, 'sent')} className="rounded px-2 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50">Send</button>
                        )}
                        {archiveView === 'active' && q.status === 'sent' && (
                          <>
                            <button onClick={() => handleStatusChange(q.id, 'accepted')} className="rounded px-2 py-1 text-xs font-medium text-green-600 hover:bg-green-50">Accept</button>
                            <button onClick={() => handleStatusChange(q.id, 'rejected')} className="rounded px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50">Reject</button>
                          </>
                        )}
                        {archiveView === 'active' && (q.status === 'sent' || q.status === 'accepted') && (
                          <button onClick={() => handleConvertToSO(q.id)} className="rounded px-2 py-1 text-xs font-medium text-purple-600 hover:bg-purple-50">→ SO</button>
                        )}
                        <button
                          onClick={() => handleArchiveToggle(q.id, archiveView === 'archived')}
                          className={`rounded px-2 py-1 text-xs font-medium ${archiveView === 'archived' ? 'text-emerald-700 hover:bg-emerald-50' : 'text-red-600 hover:bg-red-50'}`}
                        >
                          {archiveView === 'archived' ? 'Restore' : 'Archive'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!loading && <p className="border-t border-neutral-200 px-4 py-3 text-xs text-neutral-500">Showing {filteredQuotations.length} of {quotations.length} record(s)</p>}
        </div>

        {/* Create/Edit Modal */}
        {showForm && createPortal(
          <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4 backdrop-blur-sm">
            <div className="hms-card my-8 w-full max-w-4xl space-y-6 p-6">
              <h2 className="font-display text-xl font-bold text-neutral-900">
                {editingId ? 'Modify/Change Quotation' : 'New Quotation'}
              </h2>

              {error && <div className="rounded-lg bg-red-50 p-3 text-sm text-red-600">{error}</div>}

              <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                <div>
                  <label className="mb-1 block text-sm font-semibold text-neutral-700">Customer *</label>
                  <select className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={customerId} onChange={e => setCustomerId(e.target.value)}>
                    <option value="">Select Customer</option>
                    {customers.map(c => <option key={c.id} value={c.id}>{c.company_name} ({c.customer_code})</option>)}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-semibold text-neutral-700">Quotation Date *</label>
                  <input type="date" className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={quotationDate} onChange={e => setQuotationDate(e.target.value)} />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-semibold text-neutral-700">Valid Until</label>
                  <input type="date" className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={validUntil} onChange={e => setValidUntil(e.target.value)} />
                </div>
              </div>

              {/* Line Items */}
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-neutral-700">Items</h3>
                  <button onClick={addItem} className="rounded bg-primary/10 px-3 py-1.5 text-xs font-semibold text-primary hover:bg-primary/20">+ Add Item</button>
                </div>
                <div className="overflow-x-auto rounded-lg border border-neutral-200">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-neutral-50">
                        <th className="px-3 py-2 text-left">Product</th>
                        <th className="px-3 py-2 text-right w-20">Qty</th>
                        <th className="px-3 py-2 text-right w-28">Unit Price (₹)</th>
                        <th className="px-3 py-2 text-right w-20">Disc %</th>
                        <th className="px-3 py-2 text-right w-20">GST %</th>
                        <th className="px-3 py-2 text-right w-28">Total</th>
                        <th className="px-3 py-2 w-10"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((item, idx) => (
                        <tr key={idx} className="border-t border-neutral-100">
                          <td className="px-3 py-2">
                            <select className="w-full rounded border border-neutral-200 px-2 py-1.5 text-sm" value={item.product_id} onChange={e => updateItem(idx, 'product_id', e.target.value)}>
                              <option value="">Select</option>
                              {products.map(p => <option key={p.id} value={p.id}>{p.name} ({p.product_code})</option>)}
                            </select>
                          </td>
                          <td className="px-3 py-2"><input type="number" min="0.01" step="0.01" className="w-full rounded border border-neutral-200 px-2 py-1.5 text-right text-sm" value={item.quantity} onChange={e => updateItem(idx, 'quantity', parseFloat(e.target.value) || 0)} /></td>
                          <td className="px-3 py-2"><input type="number" min="0" className="w-full rounded border border-neutral-200 px-2 py-1.5 text-right text-sm" value={item.unit_price} onChange={e => updateItem(idx, 'unit_price', parseInt(e.target.value) || 0)} /></td>
                          <td className="px-3 py-2"><input type="number" min="0" max="100" className="w-full rounded border border-neutral-200 px-2 py-1.5 text-right text-sm" value={item.discount_percent || 0} onChange={e => updateItem(idx, 'discount_percent', parseFloat(e.target.value) || 0)} /></td>
                          <td className="px-3 py-2">
                            <select className="w-full rounded border border-neutral-200 px-2 py-1.5 text-sm" value={item.gst_rate} onChange={e => updateItem(idx, 'gst_rate', parseInt(e.target.value))}>
                              <option value={0}>0%</option><option value={5}>5%</option><option value={12}>12%</option><option value={18}>18%</option><option value={28}>28%</option>
                            </select>
                          </td>
                          <td className="px-3 py-2 text-right font-medium">{formatAmount(calcItemTotal(item))}</td>
                          <td className="px-3 py-2"><button onClick={() => removeItem(idx)} className="inline-flex items-center gap-1 text-red-500 hover:text-red-700"><span className="material-icons text-sm" aria-hidden="true">delete_outline</span>Remove</button></td>
                        </tr>
                      ))}
                      {items.length === 0 && <tr><td colSpan={7} className="px-3 py-4 text-center text-neutral-400">No items added</td></tr>}
                    </tbody>
                    {items.length > 0 && (
                      <tfoot>
                        <tr className="border-t-2 border-neutral-200 bg-neutral-50">
                          <td colSpan={5} className="px-3 py-2 text-right font-semibold">Grand Total:</td>
                          <td className="px-3 py-2 text-right font-bold text-primary">{formatAmount(items.reduce((sum, i) => sum + calcItemTotal(i), 0))}</td>
                          <td></td>
                        </tr>
                      </tfoot>
                    )}
                  </table>
                </div>
              </div>

              <div>
                <label className="mb-1 block text-sm font-semibold text-neutral-700">Notes</label>
                <textarea className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" rows={2} value={notes} onChange={e => setNotes(e.target.value)} />
              </div>

              <div className="flex justify-end gap-3">
                <button onClick={() => { setShowForm(false); resetForm(); }} className="rounded-lg border border-neutral-200 bg-white px-4 py-2.5 text-sm font-semibold text-neutral-600 hover:bg-neutral-50">Cancel</button>
                <button onClick={handleSubmit} disabled={submitting} className="rounded-lg bg-primary px-6 py-2.5 text-sm font-semibold text-white shadow-lg shadow-primary/20 transition hover:bg-primary/90 disabled:opacity-50">
                  {submitting ? 'Saving...' : editingId ? 'Update' : 'Create Quotation'}
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

export default QuotationsPage;

