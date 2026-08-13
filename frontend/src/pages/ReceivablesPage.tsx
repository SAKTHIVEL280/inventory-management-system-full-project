/**
 * Receivables Page (Customer Payments / Receipts)
 * Record payments from customers, allocate against invoices.
 *
 * Fixes applied:
 * - REC-001: Record Payment only allowed when invoice exists
 * - REC-003/004: Status labels 'Fully Received' / 'Partially Received'
 * - REC-005: Receivable amount cannot exceed Invoice value
 * - REC-006: Confirmation popup before marking cheque as Bounced
 * - REC-007: Confirmation popup before marking cheque as Cleared
 * - REC-008: Edit option after Recording payment (before Clear/Bounce)
 * - REC-009: Invoice number correctly linked
 */
import { useState, useEffect, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { AppLayout } from '../components/AppLayout';
import { SearchableSelect as EntitySelect, type SearchableOption } from '../components/SearchableSelect';
import { paymentsApi, type Payment, type CreatePaymentPayload, type PaymentAllocationRequest, type PaymentAllocation } from '../api/payments';
import { type SalesInvoice } from '../api/sales';
import { apiClient } from '../api/client';
import { todayLocalDateInputValue } from '../utils/date';
import { showError, showSuccess, confirmWithToast } from '../utils/toastHelper';
import { usePermissions } from '../hooks/usePermissions';
import { usePagination } from '../hooks/usePagination';
import { PaginationControls } from '../components/PaginationControls';
import { fetchAllPages } from '../utils/fetchAllPages';
import { exportToCsv, csvDateStamp } from '../utils/csvExport';

interface CustomerOption { id: string; company_name: string; customer_code?: string; phone?: string; }

const ReceivablesPage = () => {
  const { isAdmin } = usePermissions();
  const [payments, setPayments] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [customers, setCustomers] = useState<CustomerOption[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [modeFilter, setModeFilter] = useState('');
  const [archiveView, setArchiveView] = useState<'active' | 'archived'>('active');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [viewPayment, setViewPayment] = useState<Payment | null>(null);
  const [viewAllocations, setViewAllocations] = useState<PaymentAllocation[]>([]);
  const [viewLoading, setViewLoading] = useState(false);

  // Outstanding invoices for selected customer
  const [outstandingInvoices, setOutstandingInvoices] = useState<SalesInvoice[]>([]);

  // Edit mode
  const [editingPayment, setEditingPayment] = useState<Payment | null>(null);

  // Form
  const [customerId, setCustomerId] = useState('');
  const [paymentDate, setPaymentDate] = useState(todayLocalDateInputValue());
  const [amount, setAmount] = useState(0);
  const [paymentMode, setPaymentMode] = useState('bank_transfer');
  const [referenceNumber, setReferenceNumber] = useState('');
  const [notes, setNotes] = useState('');
  const [allocations, setAllocations] = useState<Record<string, number>>({});

  const fetchPayments = async () => {
    try {
      setLoading(true);
      // Fetch ALL receipts for the tenant (chunked) so the standardized pagination
      // pages through every record, not just the first API page.
      const { items } = await fetchAllPages<Payment>(async (p, size) => {
        const res = await paymentsApi.listPayments({ party_type: 'customer', archived_only: archiveView === 'archived', page: p, page_size: size });
        return { items: res.data.items || [], total: res.data.total ?? 0 };
      });
      setPayments(items);
    } catch {
      /* */
    } finally {
      setLoading(false);
    }
  };
  const fetchCustomers = async () => {
    try {
      // Load ALL active customers (chunked) so the searchable picker covers the full
      // directory. Inactive/soft-deleted customers are excluded from new receipts;
      // historical receipts still show their original name via the API (customer_name).
      const { items } = await fetchAllPages<CustomerOption>(async (p, size) => {
        const res = await apiClient.get('/api/v2/customers', { params: { page: p, page_size: size, is_active: true } });
        return { items: res.data.items || [], total: res.data.total ?? 0 };
      });
      setCustomers(items);
    } catch { /* */ }
  };

  const customerOptions: SearchableOption[] = useMemo(
    () => customers.map((c) => ({
      value: c.id,
      label: c.company_name,
      sublabel: [c.customer_code, c.phone].filter(Boolean).join(' · '),
      keywords: [c.customer_code, c.phone].filter(Boolean).join(' '),
    })),
    [customers],
  );

  // eslint-disable-next-line react-hooks/exhaustive-deps -- fetchPayments should run when archiveView changes
  useEffect(() => { fetchPayments(); }, [archiveView]);
  useEffect(() => { fetchCustomers(); }, []);

  // When customer changes, fetch ALL their outstanding invoices directly from the
  // database (MCN-BUG-03/05): every open invoice from any month or financial year,
  // not a client-side filter of the first page of the global invoice list.
  useEffect(() => {
    if (!customerId) { setOutstandingInvoices([]); return; }
    (async () => {
      try {
        // When editing, pass the payment id so the invoice(s) this payment already
        // settled are included and remain selectable (fixes "No Open Invoice" on edit).
        const res = await paymentsApi.getCustomerOpenInvoices(customerId, editingPayment?.id);
        setOutstandingInvoices((res.data.items || []) as unknown as SalesInvoice[]);
      } catch { setOutstandingInvoices([]); }
    })();
  }, [customerId, editingPayment?.id]);

  const resetForm = () => { setCustomerId(''); setPaymentDate(todayLocalDateInputValue()); setAmount(0); setPaymentMode('bank_transfer'); setReferenceNumber(''); setNotes(''); setAllocations({}); setError(''); setEditingPayment(null); };
  const paiseToRupees = (paise: number) => (Number.isFinite(paise) ? paise / 100 : 0);
  const rupeesToPaise = (value: string | number) => {
    const num = typeof value === 'number' ? value : parseFloat(value);
    return Number.isFinite(num) ? Math.round(num * 100) : 0;
  };
  const formatAmount = (p: number) => `₹${(p / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
  const formatModeLabel = (mode: string) => mode
    .replace('_', ' ')
    .split(' ')
    .map((part) => part ? part.charAt(0).toUpperCase() + part.slice(1) : part)
    .join(' ');
  const cleanNotes = (notes?: string | null) => {
    if (!notes) return '';
    return notes.replace(/\[PO_ID:[^\]]+\]/g, '').trim();
  };
  const customerNameById = (id?: string | null) => customers.find((c) => c.id === id)?.company_name || '-';
  // Prefer the API-provided name so historical receipts of a soft-deleted customer
  // still show the original customer instead of "-".
  const paymentCustomerName = (p: { customer_id?: string | null; customer_name?: string | null }) =>
    p.customer_name || customerNameById(p.customer_id);

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

  // REC-003/004: Map backend status to display labels
  const statusDisplayLabel = (status: string, display?: string) => {
    if (display && display.trim()) {
      return display;
    }
    switch (status) {
      case 'cleared': return 'Fully Received';
      case 'pending': return 'Pending';
      case 'bounced': return 'Bounced';
      case 'cancelled': return 'Cancelled';
      default: return status;
    }
  };

  const filteredPayments = payments.filter((p) => {
    const term = searchQuery.trim().toLowerCase();
    const invoiceRefs = p.allocations?.map((a) => a.invoice_number).filter(Boolean).join(' ') || '';
    const matchesSearch =
      !term ||
      paymentCustomerName(p).toLowerCase().includes(term) ||
      p.payment_date.toLowerCase().includes(term) ||
      p.status.toLowerCase().includes(term) ||
      p.payment_mode.toLowerCase().includes(term) ||
      invoiceRefs.toLowerCase().includes(term) ||
      (p.reference_number || '').toLowerCase().includes(term);
    const matchesStatus = !statusFilter || p.status === statusFilter;
    const matchesMode = !modeFilter || p.payment_mode === modeFilter;
    const matchesFrom = !dateFrom || p.payment_date >= dateFrom;
    const matchesTo = !dateTo || p.payment_date <= dateTo;
    return matchesSearch && matchesStatus && matchesMode && matchesFrom && matchesTo;
  });

  // Standardized pagination (client-side slice of the filtered, tenant-scoped list).
  // Resets to page 1 whenever any filter/search/view changes.
  const pagination = usePagination(
    JSON.stringify([searchQuery, statusFilter, modeFilter, dateFrom, dateTo, archiveView]),
  );
  const pagedPayments = pagination.paginate(filteredPayments);

  // Task 11: export the CURRENT view — filteredPayments already reflects the
  // active search, status/mode/archive filters and date range.
  const handleExport = () => {
    if (filteredPayments.length === 0) { showError('Nothing to export for the current filters'); return; }
    const headers = ['Receipt #', 'Invoice #', 'Customer', 'Date', 'Mode', 'Amount (₹)', 'Status', 'Reference #', 'Notes'];
    const rows = filteredPayments.map((p) => [
      p.payment_number || '',
      p.allocations?.map((a) => a.invoice_number).filter(Boolean).join(' | ') || '',
      paymentCustomerName(p),
      p.payment_date,
      formatModeLabel(p.payment_mode),
      (Number(p.amount || 0) / 100).toFixed(2),
      statusDisplayLabel(p.status, p.status_display),
      p.reference_number || '',
      cleanNotes(p.notes_display || p.notes),
    ]);
    exportToCsv(`receivables_${archiveView}_${csvDateStamp()}.csv`, headers, rows);
    showSuccess(`Exported ${rows.length} receipt${rows.length !== 1 ? 's' : ''}`);
  };

  const handleSubmit = async () => {
    if (!customerId || amount <= 0) { setError('Select customer and enter amount'); return; }

    // REC-001: Check that at least one open invoice exists for the customer
    if (outstandingInvoices.length === 0) {
      setError('No Open Invoice — Cannot record payment without an open invoice for this customer.');
      return;
    }

    // MCN-BUG-003: invoice allocation is mandatory — block floating receipts
    const totalAllocated = Object.values(allocations).reduce((sum, amt) => sum + (amt > 0 ? amt : 0), 0);
    if (totalAllocated <= 0) {
      setError('Please allocate the payment against at least one invoice before saving.');
      return;
    }

    // REC-005: Validate that total allocations do not exceed any individual invoice's due amount
    for (const [invoiceId, allocAmt] of Object.entries(allocations)) {
      if (allocAmt > 0) {
        const inv = outstandingInvoices.find(i => i.id === invoiceId);
        if (inv && allocAmt > inv.amount_due) {
          setError(`Allocated amount for ${inv.invoice_number} exceeds its outstanding due of ${formatAmount(inv.amount_due)}`);
          return;
        }
      }
    }

    // REC-005: Validate total payment amount does not exceed total outstanding
    const totalOutstanding = outstandingInvoices.reduce((sum, inv) => sum + inv.amount_due, 0);
    if (amount > totalOutstanding) {
      setError(`Payment amount (${formatAmount(amount)}) exceeds total outstanding receivables (${formatAmount(totalOutstanding)})`);
      return;
    }

    setSubmitting(true); setError('');
    try {
      const allocationList: PaymentAllocationRequest[] = Object.entries(allocations)
        .filter(([, amt]) => amt > 0)
        .map(([invoiceId, amt]) => ({ invoice_id: invoiceId, allocated_amount: amt }));

      const payload: CreatePaymentPayload = {
        payment_type: 'receipt', party_type: 'customer',
        customer_id: customerId, payment_date: paymentDate,
        amount: amount, payment_mode: paymentMode,
        reference_number: referenceNumber || undefined,
        notes: notes || undefined,
        allocations: allocationList,
      };
      if (editingPayment) {
        await paymentsApi.updatePayment(editingPayment.id, payload);
        showSuccess('Payment updated successfully');
      } else {
        await paymentsApi.createPayment(payload);
        showSuccess('Payment recorded successfully');
      }
      setShowForm(false); resetForm(); fetchPayments();
    } catch (err: unknown) { const m = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail; setError(typeof m === 'string' ? m : 'Failed'); } finally { setSubmitting(false); }
  };

  // REC-006: Confirmation popup for Bounced
  // REC-007: Confirmation popup for Cleared
  const handleStatusChange = async (id: string, newStatus: string) => {
    const confirmMsg = newStatus === 'bounced'
      ? 'Are you sure you want to confirm cheque bounced?'
      : newStatus === 'cleared'
        ? 'Are you sure you want to confirm cheque cleared?'
        : `Change status to ${newStatus}?`;

    const confirmType = newStatus === 'bounced' ? 'danger' : 'warning';

    const confirmed = await confirmWithToast(confirmMsg, { type: confirmType as 'confirm' | 'warning' | 'danger' });
    if (!confirmed) return;

    try {
      await paymentsApi.updatePaymentStatus(id, newStatus);
      showSuccess('Receipt status updated');
      fetchPayments();
    } catch {
      showError('Failed to update receipt status');
    }
  };

  const handleArchiveToggle = async (id: string, archived: boolean) => {
    try {
      if (archived) {
        await paymentsApi.restorePayment(id);
      } else {
        await paymentsApi.archivePayment(id);
      }
      showSuccess(archived ? 'Receipt restored' : 'Receipt archived');
      fetchPayments();
    } catch {
      showError(archived ? 'Restore failed' : 'Archive failed');
    }
  };

  // REC-008: Open edit form for a pending payment
  const handleEditPayment = (p: Payment) => {
    setEditingPayment(p);
    setCustomerId(p.customer_id || '');
    setPaymentDate(p.payment_date);
    setAmount(p.amount);
    setPaymentMode(p.payment_mode);
    setReferenceNumber(p.reference_number || '');
    setNotes('');
    // Pre-fill the existing allocations so the edit form shows how the payment is
    // currently split across invoices.
    const preAlloc: Record<string, number> = {};
    (p.allocations || []).forEach((a) => {
      if (a.invoice_id) preAlloc[a.invoice_id] = (preAlloc[a.invoice_id] || 0) + (a.allocated_amount || 0);
    });
    setAllocations(preAlloc);
    setShowForm(true);
  };

  const handleViewPayment = async (p: Payment) => {
    setViewPayment(p);
    setViewAllocations(p.allocations || []);
    setViewLoading(true);
    try {
      const res = await paymentsApi.getPayment(p.id);
      setViewPayment(res.data.payment);
      setViewAllocations(res.data.allocations || []);
    } catch {
      // Keep list data fallback for view.
    } finally {
      setViewLoading(false);
    }
  };

  const sc: Record<string, string> = { pending: 'bg-amber-100 text-amber-700', cleared: 'bg-green-100 text-green-700', bounced: 'bg-red-100 text-red-700', cancelled: 'bg-gray-100 text-gray-700' };

  // MCN-BUG-003: total allocated drives mandatory-allocation gating on the Save button
  const totalAllocatedPaise = Object.values(allocations).reduce((sum, amt) => sum + (amt > 0 ? amt : 0), 0);

  return (
    <AppLayout title="Receivables (Customer Payments)">
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <input
              type="text"
              className="w-64 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm"
              placeholder="Search customer, invoice #, ref #, status..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <select className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">All Statuses</option>
              <option value="pending">Pending</option>
              <option value="cleared">Fully Received</option>
              <option value="bounced">Bounced</option>
              <option value="cancelled">Cancelled</option>
            </select>
            <select className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm" value={modeFilter} onChange={(e) => setModeFilter(e.target.value)}>
              <option value="">All Modes</option>
              <option value="cash">Cash</option>
              <option value="bank_transfer">Bank Transfer</option>
              <option value="cheque">Cheque</option>
              <option value="upi">UPI</option>
              <option value="card">Card</option>
            </select>
            <select className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm" value={archiveView} onChange={(e) => setArchiveView(e.target.value as 'active' | 'archived')}>
              <option value="active">Active Only</option>
              <option value="archived">Archived Only</option>
            </select>
            <div className="inline-flex items-center gap-2 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm">
              <span className="text-xs font-semibold uppercase tracking-wide text-neutral-500">From</span>
              <input type="date" className="bg-transparent text-sm outline-none" value={dateFrom} max={dateTo || undefined} onChange={(e) => handleDateFromChange(e.target.value)} title="Payment date from" />
            </div>
            <div className="inline-flex items-center gap-2 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm">
              <span className="text-xs font-semibold uppercase tracking-wide text-neutral-500">To</span>
              <input type="date" className="bg-transparent text-sm outline-none" value={dateTo} min={dateFrom || undefined} onChange={(e) => handleDateToChange(e.target.value)} title="Payment date to" />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={handleExport} className="inline-flex items-center gap-1 rounded-lg border border-neutral-200 bg-white px-4 py-2.5 text-sm font-semibold text-neutral-700 hover:bg-neutral-50">
              <span className="material-icons text-base" aria-hidden="true">download</span>
              Export
            </button>
            <button onClick={() => { resetForm(); setShowForm(true); }} className="rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-primary/20 hover:bg-primary/90">+ Record Payment</button>
          </div>
        </div>

        <div className="hms-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-neutral-200 bg-neutral-50">
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Invoice #</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Customer</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Date</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Mode</th>
                <th className="px-4 py-3 text-right font-semibold text-neutral-600">Amount</th>
                <th className="px-4 py-3 text-center font-semibold text-neutral-600">Status</th>
                <th className="px-4 py-3 text-center font-semibold text-neutral-600">Actions</th>
              </tr></thead>
              <tbody>
                {loading ? <tr><td colSpan={7} className="px-4 py-8 text-center text-neutral-500">Loading...</td></tr>
                : filteredPayments.length === 0 ? <tr><td colSpan={7} className="px-4 py-8 text-center text-neutral-500">No payments recorded</td></tr>
                : pagedPayments.map(p => (
                  <tr key={p.id} className="border-b border-neutral-100 hover:bg-neutral-50">
                    <td className="px-4 py-3 font-medium">
                      {p.allocations?.map((a) => a.invoice_number).filter(Boolean).join(', ') || (
                        // MCN-BUG-003: flag legacy unallocated receipts for manual reconciliation
                        <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700" title="No invoice allocated — needs manual reconciliation">
                          <span className="material-icons text-sm" aria-hidden="true">warning</span>
                          Unallocated
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">{paymentCustomerName(p)}</td>
                    <td className="px-4 py-3">{p.payment_date}</td>
                    <td className="px-4 py-3 capitalize">{p.payment_mode.replace('_', ' ')}</td>
                    <td className="px-4 py-3 text-right font-medium">{formatAmount(p.amount)}</td>
                    <td className="px-4 py-3 text-center"><span className={`inline-block rounded-full px-2.5 py-1 text-xs font-semibold ${sc[p.status]}`}>{statusDisplayLabel(p.status, p.status_display)}</span></td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex items-center justify-center gap-1">
                        <button onClick={() => handleViewPayment(p)} className="rounded px-2 py-1 text-xs font-medium text-neutral-700 hover:bg-neutral-100">View</button>
                        {/* REC-008: Edit button for pending payments */}
                        {archiveView === 'active' && p.status === 'pending' && (
                          <>
                            <button onClick={() => handleEditPayment(p)} className="rounded px-2 py-1 text-xs font-medium text-primary hover:bg-primary/10">Edit</button>
                            {isAdmin && (
                              <>
                                <button onClick={() => handleStatusChange(p.id, 'cleared')} className="rounded px-2 py-1 text-xs font-medium text-green-600 hover:bg-green-50">Clear</button>
                                <button onClick={() => handleStatusChange(p.id, 'bounced')} className="rounded px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50">Bounced</button>
                              </>
                            )}
                          </>
                        )}
                        <button onClick={() => handleArchiveToggle(p.id, archiveView === 'archived')} className={`rounded px-2 py-1 text-xs font-medium ${archiveView === 'archived' ? 'text-emerald-700 hover:bg-emerald-50' : 'text-red-600 hover:bg-red-50'}`}>{archiveView === 'archived' ? 'Restore' : 'Archive'}</button>
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
              total={filteredPayments.length}
              onPageChange={pagination.setPage}
              onPageSizeChange={pagination.setPageSize}
              entityLabel="payments"
            />
          )}
        </div>

        {showForm && createPortal(
          <div className="fixed inset-0 z-[100] m-0 flex min-h-screen w-screen items-start justify-center overflow-y-auto bg-black/45 p-4 pt-6 backdrop-blur-sm">
            <div className="hms-card my-8 w-full max-w-2xl space-y-6 p-6">
              <h2 className="font-display text-xl font-bold">{editingPayment ? 'Edit Customer Payment' : 'Record Customer Payment'}</h2>
              {error && <div className="rounded-lg bg-red-50 p-3 text-sm text-red-600">{error}</div>}
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div>
                  <label className="mb-1 block text-sm font-semibold text-neutral-700">Customer *</label>
                  <EntitySelect
                    value={customerId}
                    options={customerOptions}
                    onChange={setCustomerId}
                    className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm outline-none focus:border-primary"
                    placeholder="Search customer by name, code, phone…"
                    emptyMessage="No matching customer"
                  />
                </div>
                <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Date *</label><input type="date" className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={paymentDate} onChange={e => setPaymentDate(e.target.value)} /></div>
                <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Amount (₹) *</label><input type="number" step="0.01" min="0.01" className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={amount > 0 ? paiseToRupees(amount) : ''} onChange={e => setAmount(rupeesToPaise(e.target.value))} /></div>
                <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Mode</label><select className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={paymentMode} onChange={e => setPaymentMode(e.target.value)}><option value="cash">Cash</option><option value="bank_transfer">Bank Transfer</option><option value="cheque">Cheque</option><option value="upi">UPI</option><option value="card">Card</option></select></div>
                <div className="md:col-span-2"><label className="mb-1 block text-sm font-semibold text-neutral-700">Reference #</label><input type="text" className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={referenceNumber} onChange={e => setReferenceNumber(e.target.value)} /></div>
              </div>

              {/* REC-001: Show message when no invoices exist */}
              {customerId && outstandingInvoices.length === 0 && (
                <div className="rounded-lg bg-amber-50 border border-amber-200 p-3 text-sm text-amber-700 font-medium">
                  No Open Invoice — This customer has no outstanding invoices.
                </div>
              )}

              {outstandingInvoices.length > 0 && (
                <div>
                  <h3 className="mb-2 text-sm font-semibold text-neutral-700">Allocate to Invoices <span className="text-red-500">*</span></h3>
                  <div className="rounded-lg border border-neutral-200">
                    <table className="w-full text-sm">
                      <thead><tr className="bg-neutral-50"><th className="px-3 py-2 text-left">Invoice</th><th className="px-3 py-2 text-right">Due</th><th className="px-3 py-2 text-right w-32">Allocate</th></tr></thead>
                      <tbody>
                        {outstandingInvoices.map(inv => (
                          <tr key={inv.id} className="border-t border-neutral-100">
                            <td className="px-3 py-2">{inv.invoice_number}</td>
                            <td className="px-3 py-2 text-right">{formatAmount(inv.amount_due)}</td>
                            <td className="px-3 py-2"><input type="number" step="0.01" min="0" max={paiseToRupees(inv.amount_due)} className="w-full rounded border px-2 py-1.5 text-right text-sm" value={allocations[inv.id] ? paiseToRupees(allocations[inv.id]) : ''} onChange={e => {
                              const newVal = rupeesToPaise(e.target.value);
                              // REC-005: Clamp allocation to invoice due
                              const clamped = Math.min(newVal, inv.amount_due);
                              setAllocations({ ...allocations, [inv.id]: clamped });
                            }} /></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {/* MCN-BUG-003: inline mandatory-allocation hint */}
                  {totalAllocatedPaise <= 0 && (
                    <p className="mt-2 text-xs font-medium text-red-600">
                      Please allocate the payment against at least one invoice before saving.
                    </p>
                  )}
                </div>
              )}

              <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Notes</label><textarea className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" rows={2} value={notes} onChange={e => setNotes(e.target.value)} /></div>
              <div className="flex justify-end gap-3">
                <button onClick={() => { setShowForm(false); resetForm(); }} className="rounded-lg border border-neutral-200 bg-white px-4 py-2.5 text-sm font-semibold text-neutral-600">Cancel</button>
                <button onClick={handleSubmit} disabled={submitting || (customerId !== '' && outstandingInvoices.length === 0) || totalAllocatedPaise <= 0} className="rounded-lg bg-primary px-6 py-2.5 text-sm font-semibold text-white shadow-lg shadow-primary/20 disabled:opacity-50">{submitting ? 'Recording...' : 'Record Payment'}</button>
              </div>
            </div>
          </div>,
          document.body
        )}

        {viewPayment && createPortal(
          <div className="fixed inset-0 z-[110] m-0 flex min-h-screen w-screen items-start justify-center overflow-y-auto bg-black/45 p-4 pt-6 backdrop-blur-sm" onClick={() => { setViewPayment(null); setViewAllocations([]); }}>
            <div className="hms-card my-8 w-full max-w-3xl space-y-6 p-6" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="font-display text-xl font-bold">Customer Payment</h2>
                  <p className="text-sm text-neutral-600">{viewPayment.payment_number}</p>
                </div>
                <button onClick={() => { setViewPayment(null); setViewAllocations([]); }} className="text-neutral-400 hover:text-neutral-600 text-2xl">&times;</button>
              </div>

              {viewLoading ? (
                <p className="text-sm text-neutral-500">Loading details...</p>
              ) : (
                <>
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <div><p className="text-xs text-neutral-600">Customer</p><p className="font-medium">{paymentCustomerName(viewPayment)}</p></div>
                    <div><p className="text-xs text-neutral-600">Date</p><p className="font-medium">{viewPayment.payment_date}</p></div>
                    <div><p className="text-xs text-neutral-600">Mode</p><p className="font-medium">{formatModeLabel(viewPayment.payment_mode)}</p></div>
                    <div><p className="text-xs text-neutral-600">Amount</p><p className="font-medium">{formatAmount(viewPayment.amount)}</p></div>
                    <div><p className="text-xs text-neutral-600">Status</p><p className="font-medium">{statusDisplayLabel(viewPayment.status, viewPayment.status_display)}</p></div>
                    <div><p className="text-xs text-neutral-600">Reference #</p><p className="font-medium">{viewPayment.reference_number || '—'}</p></div>
                    <div className="md:col-span-2"><p className="text-xs text-neutral-600">Notes</p><p className="font-medium">{cleanNotes(viewPayment.notes_display || viewPayment.notes) || '—'}</p></div>
                  </div>

                  <div>
                    <h3 className="mb-2 text-sm font-semibold text-neutral-700">Allocations</h3>
                    {viewAllocations.length === 0 ? (
                      <p className="text-sm text-neutral-500">No allocations.</p>
                    ) : (
                      <div className="overflow-x-auto rounded-lg border border-neutral-200">
                        <table className="w-full text-sm">
                          <thead><tr className="bg-neutral-50"><th className="px-3 py-2 text-left">Invoice</th><th className="px-3 py-2 text-right">Allocated</th></tr></thead>
                          <tbody>
                            {viewAllocations.map((a, idx) => (
                              <tr key={`${a.invoice_id || 'invoice'}-${idx}`} className="border-t border-neutral-100">
                                <td className="px-3 py-2">{a.invoice_number || 'Unallocated'}</td>
                                <td className="px-3 py-2 text-right">{formatAmount(a.allocated_amount)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>,
          document.body
        )}
      </div>
    </AppLayout>
  );
};

export default ReceivablesPage;

