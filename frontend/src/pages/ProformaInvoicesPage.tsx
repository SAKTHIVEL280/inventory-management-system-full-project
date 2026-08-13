/**
 * Proforma Invoices Page
 * Independent replica of QuotationsPage. List, create, edit proforma invoices.
 * Approve, download/send PDF. Behaviour identical to Quotation; only labels,
 * numbering (PFI-…) and module identity differ.
 */
import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { AppLayout } from '../components/AppLayout';
import { PaginationControls } from '../components/PaginationControls';
import { usePagination } from '../hooks/usePagination';
import { fetchAllPages } from '../utils/fetchAllPages';
import { proformaApi, type ProformaInvoice, type CreateProformaInvoicePayload } from '../api/proforma';
import type { SalesLineItem } from '../api/sales';
import { apiClient } from '../api/client';
import { toast } from 'sonner';
import { dateInputValueAfterDays, todayLocalDateInputValue } from '../utils/date';
import { emptyWhenZero } from '../utils/numberInput';
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

const ProformaInvoicesPage = () => {
  const [proformaInvoices, setProformaInvoices] = useState<ProformaInvoice[]>([]);
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
  const [proformaDate, setProformaDate] = useState(todayLocalDateInputValue());
  const [validUntil, setValidUntil] = useState('');
  const [notes, setNotes] = useState('');
  const [items, setItems] = useState<SalesLineItem[]>([]);

  const fetchProformaInvoices = async () => {
    try {
      setLoading(true);
      // Fetch the complete tenant dataset (chunked) for full client-side filtering + pagination.
      const { items } = await fetchAllPages<ProformaInvoice>(async (p, size) => {
        const res = await proformaApi.listProformaInvoices(statusFilter || undefined, p, size, {
          archived_only: archiveView === 'archived',
        });
        return { items: res.data.items || [], total: res.data.total ?? 0 };
      });
      setProformaInvoices(items);
    } catch {
      setError('Failed to load proforma invoices');
    } finally {
      setLoading(false);
    }
  };

  const fetchMasterData = async () => {
    try {
      const [custList, prodRes] = await Promise.all([
        // Load ALL customers (chunked) so none are hidden by a page-size cap.
        fetchAllPages<CustomerOption>(async (pageNo, size) => {
          const res = await apiClient.get('/api/v2/customers', { params: { page: pageNo, page_size: size } });
          return { items: res.data.items || [], total: res.data.total ?? 0 };
        }),
        // all_products=true returns the complete catalogue (no page cap).
        apiClient.get('/api/v2/products', { params: { all_products: true } }),
      ]);
      setCustomers(custList.items);
      setProducts(prodRes.data.items || []);
    } catch {
      /* ignore */
    }
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps -- should run on status/archive filter changes
  useEffect(() => { fetchProformaInvoices(); }, [statusFilter, archiveView]);
  useEffect(() => { fetchMasterData(); }, []);

  const resetForm = () => {
    setCustomerId('');
    setProformaDate(todayLocalDateInputValue());
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
    // Auto-fill MRP and GST when product selected
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

  // Load proforma invoice data for editing
  const handleEdit = async (p: ProformaInvoice) => {
    try {
      const { data } = await proformaApi.getProformaInvoice(p.id);
      const detail = (data as unknown as { proforma_invoice: ProformaInvoice; items: Array<{ product_id: string; quantity: number; unit_price: number; discount_percent: number; gst_rate: number }> });
      setCustomerId(detail.proforma_invoice.customer_id);
      setProformaDate(detail.proforma_invoice.proforma_date);
      setValidUntil(detail.proforma_invoice.valid_until || '');
      setNotes(detail.proforma_invoice.notes || '');
      setItems(detail.items.map((i) => ({
        product_id: i.product_id,
        quantity: i.quantity,
        unit_price: i.unit_price,
        discount_percent: i.discount_percent,
        gst_rate: i.gst_rate,
      })));
      setEditingId(p.id);
      setShowForm(true);
    } catch {
      toast.error('Failed to load proforma invoice for editing');
    }
  };

  const handleSubmit = async () => {
    if (!customerId || items.length === 0) {
      setError('Please select a customer and add at least one item');
      return;
    }
    // Frontend validation for Valid Until
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
      const payload: CreateProformaInvoicePayload = {
        customer_id: customerId,
        proforma_date: proformaDate,
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
        await proformaApi.updateProformaInvoice(editingId, payload);
      } else {
        await proformaApi.createProformaInvoice(payload);
      }
      setShowForm(false);
      resetForm();
      fetchProformaInvoices();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(typeof msg === 'string' ? msg : 'Failed to save proforma invoice');
    } finally {
      setSubmitting(false);
    }
  };

  const handleStatusChange = async (id: string, newStatus: string) => {
    try {
      await proformaApi.updateProformaInvoiceStatus(id, newStatus);
      toast.success(newStatus === 'sent' ? 'Proforma Invoice approved' : 'Proforma Invoice status updated');
      fetchProformaInvoices();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(typeof msg === 'string' ? msg : 'Status update failed');
    }
  };

  const handleArchiveToggle = async (id: string, archived: boolean) => {
    try {
      if (archived) {
        await proformaApi.restoreProformaInvoice(id);
      } else {
        await proformaApi.archiveProformaInvoice(id);
      }
      toast.success(archived ? 'Proforma Invoice restored' : 'Proforma Invoice archived');
      fetchProformaInvoices();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(typeof msg === 'string' ? msg : archived ? 'Restore failed' : 'Archive failed');
    }
  };

  const handleDownloadPDF = async (p: ProformaInvoice) => {
    try {
      toast.info('Generating PDF...');
      const response = await proformaApi.downloadProformaInvoicePdf(p.id);
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `ProformaInvoice-${p.proforma_number}.pdf`);
      document.body.appendChild(link);
      link.click();
      window.URL.revokeObjectURL(url);
      link.remove();
      toast.success('PDF downloaded successfully');
    } catch {
      toast.error('Failed to download PDF');
    }
  };

  const handleSendPDF = async (p: ProformaInvoice) => {
    try {
      await proformaApi.sendProformaInvoiceEmail(p.id);
      toast.success(`Proforma Invoice ${p.proforma_number} queued for sending`);
    } catch {
      toast.error('Failed to queue proforma invoice email');
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

  const filteredProformaInvoices = proformaInvoices.filter((p) => {
    const term = searchQuery.trim().toLowerCase();
    const customerName = customerNameById(p.customer_id).toLowerCase();
    const matchesSearch =
      !term ||
      p.proforma_number.toLowerCase().includes(term) ||
      customerName.includes(term) ||
      p.status.toLowerCase().includes(term) ||
      p.proforma_date.toLowerCase().includes(term) ||
      (p.valid_until || '').toLowerCase().includes(term);
    const matchesFrom = !dateFrom || p.proforma_date >= dateFrom;
    const matchesTo = !dateTo || p.proforma_date <= dateTo;
    return matchesSearch && matchesFrom && matchesTo;
  });

  // Standardized pagination (client-side slice of the filtered, tenant-scoped list).
  const pagination = usePagination(JSON.stringify([searchQuery, statusFilter, dateFrom, dateTo]));
  const pagedProformaInvoices = pagination.paginate(filteredProformaInvoices);

  return (
    <AppLayout title="Proforma Invoices">
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
              placeholder="Search proforma invoice #, customer, status..."
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
                title="Proforma Invoice date from"
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
                title="Proforma Invoice date to"
              />
            </div>
          </div>
          <button
            onClick={() => { resetForm(); setShowForm(true); }}
            className="rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-primary/20 transition hover:bg-primary/90"
          >
            + New Proforma Invoice
          </button>
        </div>

        {/* Table */}
        <div className="hms-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-neutral-200 bg-neutral-50">
                  <th className="px-4 py-3 text-left font-semibold text-neutral-600">Proforma Invoice Number</th>
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
                ) : filteredProformaInvoices.length === 0 ? (
                  <tr><td colSpan={7} className="px-4 py-8 text-center text-neutral-500">No proforma invoices found</td></tr>
                ) : pagedProformaInvoices.map(p => (
                  <tr key={p.id} className="border-b border-neutral-100 hover:bg-neutral-50">
                    <td className="px-4 py-3 font-medium">{p.proforma_number}</td>
                    <td className="px-4 py-3">{customerNameById(p.customer_id)}</td>
                    <td className="px-4 py-3">{p.proforma_date}</td>
                    <td className="px-4 py-3">{p.valid_until || '-'}</td>
                    <td className="px-4 py-3 text-right font-medium">{formatAmount(p.total_amount)}</td>
                    <td className="px-4 py-3 text-center">
                      <span className={`inline-block rounded-full px-2.5 py-1 text-xs font-semibold ${statusColors[p.status] || 'bg-gray-100'}`}>
                        {p.status === 'sent' ? 'approved' : p.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex items-center justify-center gap-1">
                        {archiveView === 'active' && (p.status === 'draft' || p.status === 'sent') && (
                          <button onClick={() => handleEdit(p)} className="rounded px-2 py-1 text-xs font-medium text-primary hover:bg-primary/10">Edit</button>
                        )}
                        {isAdmin && archiveView === 'active' && p.status === 'draft' && (
                          <button onClick={() => handleStatusChange(p.id, 'sent')} className="rounded px-2 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50">Approve</button>
                        )}
                        {isAdmin && archiveView === 'active' && p.status === 'sent' && (
                          <>
                            <button onClick={() => handleStatusChange(p.id, 'accepted')} className="rounded px-2 py-1 text-xs font-medium text-green-600 hover:bg-green-50">Accept</button>
                            <button onClick={() => handleStatusChange(p.id, 'rejected')} className="rounded px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50">Reject</button>
                          </>
                        )}
                        <button
                          onClick={() => handleDownloadPDF(p)}
                          className="inline-flex items-center gap-1 rounded border border-neutral-200 bg-white px-2 py-1 text-xs font-semibold text-neutral-700 hover:bg-neutral-50"
                          title="Download PDF"
                        >
                          <span className="material-icons text-sm" aria-hidden="true">picture_as_pdf</span>
                          PDF
                        </button>
                        <button
                          onClick={() => handleSendPDF(p)}
                          className="rounded px-2 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-50"
                        >
                          Send PDF
                        </button>
                        <button
                          onClick={() => handleArchiveToggle(p.id, archiveView === 'archived')}
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
              total={filteredProformaInvoices.length}
              onPageChange={pagination.setPage}
              onPageSizeChange={pagination.setPageSize}
              entityLabel="proforma invoices"
            />
          )}
        </div>

        {/* Create/Edit Modal */}
        {showForm && createPortal(
          <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-2 sm:p-4 backdrop-blur-sm">
            <div className="hms-card my-4 sm:my-8 w-[min(96vw,1500px)] max-w-none space-y-6 p-4 sm:p-6">
              <h2 className="font-display text-xl font-bold text-neutral-900">
                {editingId ? 'Modify/Change Proforma Invoice' : 'New Proforma Invoice'}
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
                  <label className="mb-1 block text-sm font-semibold text-neutral-700">Proforma Invoice Date *</label>
                  <input type="date" className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={proformaDate} onChange={e => setProformaDate(e.target.value)} />
                </div>
                <div>
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

              {/* Line Items - MRP, Product Code, Description columns */}
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
                            <td className="px-3 py-2 text-xs text-neutral-500 font-mono">{prod?.product_code || '-'}</td>
                            <td className="px-3 py-2 text-xs text-neutral-500">{prod?.description || prod?.name || '-'}</td>
                            <td className="px-3 py-2"><input type="number" min="0.01" step="0.01" className="w-full rounded border border-neutral-200 px-2 py-1.5 text-right text-sm" value={item.quantity} onChange={e => updateItem(idx, 'quantity', parseFloat(e.target.value) || 0)} /></td>
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
                  {submitting ? 'Saving...' : editingId ? 'Update' : 'Create Proforma Invoice'}
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

export default ProformaInvoicesPage;
