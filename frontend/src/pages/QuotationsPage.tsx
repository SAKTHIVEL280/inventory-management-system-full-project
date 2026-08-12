/**
 * Quotations Page
 * List, create, edit quotations. Approve, download/send PDF.
 *
 * SAL-003: MRP instead of Unit Price
 * SAL-004: Product Code column
 * SAL-005: Product Description column
 * SAL-006: Valid Until must be future date
 * SAL-007: Removed SO reference/convert
 * SAL-008: Renamed Send â†’ Approve
 * SAL-009: Download PDF
 * SAL-010: Send PDF
 * SAL-011: Quotation output format same as Tax Invoice
 * SAL-012: Edit option after creation
 */
import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { AppLayout } from '../components/AppLayout';
import { PaginationControls } from '../components/PaginationControls';
import { usePagination } from '../hooks/usePagination';
import { fetchAllPages } from '../utils/fetchAllPages';
import { salesApi, type Quotation, type CreateQuotationPayload, type SalesLineItem } from '../api/sales';
import { apiClient } from '../api/client';
import { toast } from 'sonner';
import { dateInputValueAfterDays, todayLocalDateInputValue } from '../utils/date';
import { emptyWhenZero } from '../utils/numberInput';
import { parseWholeQuantity } from '../utils/quantityValidation';
import { usePermissions } from '../hooks/usePermissions';

interface ProductOption {
  id: string;
  name: string;
  product_code: string;
  description?: string;
  selling_price: number;
  mrp: number;
  gst_rate: number;
  hsn_code: string;
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
  const { isAdmin } = usePermissions();

  // Form state
  const [customerId, setCustomerId] = useState('');
  const [quotationDate, setQuotationDate] = useState(todayLocalDateInputValue());
  const [validUntil, setValidUntil] = useState('');
  const [notes, setNotes] = useState('');
  const [items, setItems] = useState<SalesLineItem[]>([]);

  const fetchQuotations = async () => {
    try {
      setLoading(true);
      // Fetch the complete tenant dataset (chunked) so client-side filtering +
      // pagination see every record, not just the first page.
      const { items } = await fetchAllPages<Quotation>(async (p, size) => {
        const res = await salesApi.listQuotations(statusFilter || undefined, p, size, {
          archived_only: archiveView === 'archived',
        });
        return { items: res.data.items || [], total: res.data.total ?? 0 };
      });
      setQuotations(items);
    } catch {
      setError('Failed to load quotations');
    } finally {
      setLoading(false);
    }
  };

  const fetchMasterData = async () => {
    try {
      const [custRes, prodRes] = await Promise.all([
        apiClient.get('/api/v2/customers', { params: { page_size: 100 } }),
        apiClient.get('/api/v2/products', { params: { page_size: 100 } }),
      ]);
      setCustomers(custRes.data.items || []);
      setProducts(prodRes.data.items || []);
    } catch {
      /* ignore */
    }
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps -- fetchQuotations should run on status/archive filter changes
  useEffect(() => { fetchQuotations(); }, [statusFilter, archiveView]);
  useEffect(() => { fetchMasterData(); }, []);

  const resetForm = () => {
    setCustomerId('');
    setQuotationDate(todayLocalDateInputValue());
    setValidUntil('');
    setNotes('');
    setItems([]);
    setEditingId(null);
    setError('');
  };

  const addItem = () => {
    setItems([...items, { product_id: '', quantity: 1, unit_price: 0, discount_percent: 0, gst_rate: 18 }]);
  };

  const paiseToRupees = (paise: number) => (Number.isFinite(paise) ? paise / 100 : 0);
  const rupeesToPaise = (value: string | number) => {
    const num = typeof value === 'number' ? value : parseFloat(value);
    return Number.isFinite(num) ? Math.round(num * 100) : 0;
  };

  const updateItem = (index: number, field: keyof SalesLineItem, value: string | number) => {
    const updated = [...items];
    (updated[index] as unknown as Record<string, unknown>)[field] = value;
    // SAL-003: Auto-fill MRP and GST when product selected
    if (field === 'product_id') {
      const product = products.find(p => p.id === value);
      if (product) {
        updated[index].unit_price = product.mrp || product.selling_price;
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

  // SAL-012: Load quotation data for editing
  const handleEdit = async (q: Quotation) => {
    try {
      const { data } = await salesApi.getQuotation(q.id);
      const quotation = (data as unknown as { quotation: Quotation; items: Array<{ product_id: string; quantity: number; unit_price: number; discount_percent: number; gst_rate: number }> });
      setCustomerId(quotation.quotation.customer_id);
      setQuotationDate(quotation.quotation.quotation_date);
      setValidUntil(quotation.quotation.valid_until || '');
      setNotes(quotation.quotation.notes || '');
      setItems(quotation.items.map((i) => ({
        product_id: i.product_id,
        quantity: i.quantity,
        unit_price: i.unit_price,
        discount_percent: i.discount_percent,
        gst_rate: i.gst_rate,
      })));
      setEditingId(q.id);
      setShowForm(true);
    } catch {
      toast.error('Failed to load quotation for editing');
    }
  };

  const handleSubmit = async () => {
    if (!customerId || items.length === 0) {
      setError('Please select a customer and add at least one item');
      return;
    }
    // SAL-006: Frontend validation for Valid Until
    if (validUntil) {
      const today = todayLocalDateInputValue();
      if (validUntil <= today) {
        setError('Valid Until date must be a future date');
        return;
      }
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

  // SAL-008: Renamed from Send to Approve
  const handleStatusChange = async (id: string, newStatus: string) => {
    try {
      await salesApi.updateQuotationStatus(id, newStatus);
      toast.success(newStatus === 'sent' ? 'Quotation approved' : 'Quotation status updated');
      fetchQuotations();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(typeof msg === 'string' ? msg : 'Status update failed');
    }
  };

  const handleArchiveToggle = async (id: string, archived: boolean) => {
    try {
      if (archived) {
        await salesApi.restoreQuotation(id);
      } else {
        await salesApi.archiveQuotation(id);
      }
      toast.success(archived ? 'Quotation restored' : 'Quotation archived');
      fetchQuotations();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(typeof msg === 'string' ? msg : archived ? 'Restore failed' : 'Archive failed');
    }
  };

  // SAL-009: Download PDF
  const handleDownloadPDF = async (q: Quotation) => {
    try {
      toast.info('Generating PDF...');
      const response = await salesApi.downloadQuotationPdf(q.id);
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `Quotation-${q.quotation_number}.pdf`);
      document.body.appendChild(link);
      link.click();
      window.URL.revokeObjectURL(url);
      link.remove();
      toast.success('PDF downloaded successfully');
    } catch {
      toast.error('Failed to download PDF');
    }
  };

  const handleSendPDF = async (q: Quotation) => {
    try {
      await salesApi.sendQuotationEmail(q.id);
      toast.success(`Quotation ${q.quotation_number} queued for sending`);
    } catch {
      toast.error('Failed to queue quotation email');
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

  // Helper to get product info by ID
  const productById = (id: string) => products.find((p) => p.id === id);

  const handleDateFromChange = (value: string) => {
    setDateFrom(value);
    if (dateTo && value && value > dateTo) {
      setDateTo(value);
    }
  };

  const handleDateToChange = (value: string) => {
    setDateTo(value);
    if (dateFrom && value && value < dateFrom) {
      setDateFrom(value);
    }
  };

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

  // Standardized pagination (client-side slice of the filtered, tenant-scoped list).
  const pagination = usePagination(JSON.stringify([searchQuery, statusFilter, dateFrom, dateTo]));
  const pagedQuotations = pagination.paginate(filteredQuotations);

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
              <option value="sent">Approved</option>
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
                max={dateTo || undefined}
                onChange={(e) => handleDateFromChange(e.target.value)}
                title="Quotation date from"
              />
            </div>
            <div className="inline-flex items-center gap-2 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm">
              <span className="text-xs font-semibold uppercase tracking-wide text-neutral-500">To</span>
              <input
                type="date"
                className="bg-transparent text-sm outline-none"
                value={dateTo}
                min={dateFrom || undefined}
                onChange={(e) => handleDateToChange(e.target.value)}
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
                  <th className="px-4 py-3 text-left font-semibold text-neutral-600">Quotation Number</th>
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
                ) : pagedQuotations.map(q => (
                  <tr key={q.id} className="border-b border-neutral-100 hover:bg-neutral-50">
                    <td className="px-4 py-3 font-medium">{q.quotation_number}</td>
                    <td className="px-4 py-3">{customerNameById(q.customer_id)}</td>
                    <td className="px-4 py-3">{q.quotation_date}</td>
                    <td className="px-4 py-3">{q.valid_until || '-'}</td>
                    <td className="px-4 py-3 text-right font-medium">{formatAmount(q.total_amount)}</td>
                    <td className="px-4 py-3 text-center">
                      <span className={`inline-block rounded-full px-2.5 py-1 text-xs font-semibold ${statusColors[q.status] || 'bg-gray-100'}`}>
                        {q.status === 'sent' ? 'approved' : q.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex items-center justify-center gap-1">
                        {/* SAL-012: Edit button for draft/sent */}
                        {archiveView === 'active' && (q.status === 'draft' || q.status === 'sent') && (
                          <button onClick={() => handleEdit(q)} className="rounded px-2 py-1 text-xs font-medium text-primary hover:bg-primary/10">Edit</button>
                        )}
                        {/* SAL-008: Renamed Send â†’ Approve */}
                        {isAdmin && archiveView === 'active' && q.status === 'draft' && (
                          <button onClick={() => handleStatusChange(q.id, 'sent')} className="rounded px-2 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50">Approve</button>
                        )}
                        {isAdmin && archiveView === 'active' && q.status === 'sent' && (
                          <>
                            <button onClick={() => handleStatusChange(q.id, 'accepted')} className="rounded px-2 py-1 text-xs font-medium text-green-600 hover:bg-green-50">Accept</button>
                            <button onClick={() => handleStatusChange(q.id, 'rejected')} className="rounded px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50">Reject</button>
                          </>
                        )}
                        {/* SAL-009: Download PDF */}
                        <button
                          onClick={() => handleDownloadPDF(q)}
                          className="inline-flex items-center gap-1 rounded border border-neutral-200 bg-white px-2 py-1 text-xs font-semibold text-neutral-700 hover:bg-neutral-50"
                          title="Download PDF"
                        >
                          <span className="material-icons text-sm" aria-hidden="true">picture_as_pdf</span>
                          PDF
                        </button>
                        <button
                          onClick={() => handleSendPDF(q)}
                          className="rounded px-2 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-50"
                        >
                          Send PDF
                        </button>
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
          {!loading && (
            <PaginationControls
              page={pagination.page}
              pageSize={pagination.pageSize}
              total={filteredQuotations.length}
              onPageChange={pagination.setPage}
              onPageSizeChange={pagination.setPageSize}
              entityLabel="quotations"
            />
          )}
        </div>

        {/* Create/Edit Modal */}
        {showForm && createPortal(
          <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-2 sm:p-4 backdrop-blur-sm">
            <div className="hms-card my-4 sm:my-8 w-[min(96vw,1500px)] max-w-none space-y-6 p-4 sm:p-6">
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
                  {/* SAL-006: Valid Until with future date hint */}
                  <label className="mb-1 block text-sm font-semibold text-neutral-700">Valid Until <span className="text-xs text-neutral-400">(must be future date)</span></label>
                  <input
                    type="date"
                    className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm"
                    value={validUntil}
                    min={dateInputValueAfterDays(1)}
                    onChange={e => setValidUntil(e.target.value)}
                  />
                </div>
              </div>

              {/* Line Items - SAL-003/004/005: MRP, Product Code, Description columns */}
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
                        <th className="px-3 py-2 text-left w-24">Product Code</th>
                        <th className="px-3 py-2 text-left w-32">Description</th>
                        <th className="px-3 py-2 text-right w-20">Qty</th>
                        <th className="px-3 py-2 text-right w-28">MRP (₹)</th>
                        <th className="px-3 py-2 text-right w-20">Disc %</th>
                        <th className="px-3 py-2 text-right w-20">GST %</th>
                        <th className="px-3 py-2 text-right w-28">Total</th>
                        <th className="px-3 py-2 w-10"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((item, idx) => {
                        const prod = productById(item.product_id);
                        return (
                          <tr key={idx} className="border-t border-neutral-100">
                            <td className="px-3 py-2">
                              <select className="w-full rounded border border-neutral-200 px-2 py-1.5 text-sm" value={item.product_id} onChange={e => updateItem(idx, 'product_id', e.target.value)}>
                                <option value="">Select</option>
                                {products.map(p => <option key={p.id} value={p.id}>{p.name} ({p.product_code})</option>)}
                              </select>
                            </td>
                            {/* SAL-004: Product Code column */}
                            <td className="px-3 py-2 text-xs text-neutral-500 font-mono">{prod?.product_code || '-'}</td>
                            {/* SAL-005: Description column */}
                            <td className="px-3 py-2 text-xs text-neutral-500">{prod?.description || prod?.name || '-'}</td>
                            <td className="px-3 py-2"><input type="number" min="1" step="1" className="w-full rounded border border-neutral-200 px-2 py-1.5 text-right text-sm" value={item.quantity} onChange={e => updateItem(idx, 'quantity', parseWholeQuantity(e.target.value))} onKeyDown={e => { if (e.key === '.' || e.key === 'e') e.preventDefault(); }} /></td>
                            {/* SAL-003: MRP column */}
                            <td className="px-3 py-2"><input type="number" min="0" step="0.01" className="w-full rounded border border-neutral-200 px-2 py-1.5 text-right text-sm" value={item.unit_price ? paiseToRupees(item.unit_price) : ''} onChange={e => updateItem(idx, 'unit_price', rupeesToPaise(e.target.value))} /></td>
                            <td className="px-3 py-2"><input type="number" min="0" max="100" className="w-full rounded border border-neutral-200 px-2 py-1.5 text-right text-sm" value={emptyWhenZero(item.discount_percent)} onChange={e => updateItem(idx, 'discount_percent', parseFloat(e.target.value) || 0)} /></td>
                            <td className="px-3 py-2">
                              <select className="w-full rounded border border-neutral-200 px-2 py-1.5 text-sm" value={item.gst_rate} onChange={e => updateItem(idx, 'gst_rate', parseInt(e.target.value))}>
                                <option value={0}>0%</option><option value={5}>5%</option><option value={12}>12%</option><option value={18}>18%</option><option value={28}>28%</option>
                              </select>
                            </td>
                            <td className="px-3 py-2 text-right font-medium">{formatAmount(calcItemTotal(item))}</td>
                            <td className="px-3 py-2"><button onClick={() => removeItem(idx)} className="inline-flex items-center gap-1 text-red-500 hover:text-red-700"><span className="material-icons text-sm" aria-hidden="true">delete_outline</span>Remove</button></td>
                          </tr>
                        );
                      })}
                      {items.length === 0 && <tr><td colSpan={9} className="px-3 py-4 text-center text-neutral-400">No items added</td></tr>}
                    </tbody>
                    {items.length > 0 && (
                      <tfoot>
                        <tr className="border-t-2 border-neutral-200 bg-neutral-50">
                          <td colSpan={7} className="px-3 py-2 text-right font-semibold">Grand Total:</td>
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

