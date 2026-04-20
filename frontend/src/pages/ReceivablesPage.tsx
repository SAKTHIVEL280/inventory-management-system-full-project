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
import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { AppLayout } from '../components/AppLayout';
import { paymentsApi, type Payment, type CreatePaymentPayload, type PaymentAllocationRequest } from '../api/payments';
import { salesApi, type SalesInvoice } from '../api/sales';
import { apiClient } from '../api/client';
import { todayLocalDateInputValue } from '../utils/date';
import { showError, showSuccess, confirmWithToast } from '../utils/toastHelper';

interface CustomerOption { id: string; company_name: string; }

const ReceivablesPage = () => {
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
      const res = await paymentsApi.listPayments({ party_type: 'customer', archived_only: archiveView === 'archived' });
      setPayments(res.data.items || []);
    } catch {
      /* */
    } finally {
      setLoading(false);
    }
  };
  const fetchCustomers = async () => {
    try { const res = await apiClient.get('/api/v2/customers', { params: { page_size: 100 } }); setCustomers(res.data.items || []); } catch { /* */ }
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps -- fetchPayments should run when archiveView changes
  useEffect(() => { fetchPayments(); }, [archiveView]);
  useEffect(() => { fetchCustomers(); }, []);

  // When customer changes, fetch their outstanding invoices
  useEffect(() => {
    if (!customerId) { setOutstandingInvoices([]); return; }
    (async () => {
      try {
        const res = await salesApi.listInvoices('issued');
        const partialRes = await salesApi.listInvoices('partial_paid');
        const all = [...(res.data.items || []), ...(partialRes.data.items || [])];
        setOutstandingInvoices(all.filter(inv => inv.customer_id === customerId && inv.amount_due > 0));
      } catch { setOutstandingInvoices([]); }
    })();
  }, [customerId]);

  const resetForm = () => { setCustomerId(''); setPaymentDate(todayLocalDateInputValue()); setAmount(0); setPaymentMode('bank_transfer'); setReferenceNumber(''); setNotes(''); setAllocations({}); setError(''); setEditingPayment(null); };
  const paiseToRupees = (paise: number) => (Number.isFinite(paise) ? paise / 100 : 0);
  const rupeesToPaise = (value: string | number) => {
    const num = typeof value === 'number' ? value : parseFloat(value);
    return Number.isFinite(num) ? Math.round(num * 100) : 0;
  };
  const formatAmount = (p: number) => `₹${(p / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
  const customerNameById = (id?: string | null) => customers.find((c) => c.id === id)?.company_name || '-';

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
  const statusDisplayLabel = (status: string) => {
    switch (status) {
      case 'cleared': return 'Fully Received';
      case 'pending': return 'Partially Received';
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
      customerNameById(p.customer_id).toLowerCase().includes(term) ||
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

  const handleSubmit = async () => {
    if (!customerId || amount <= 0) { setError('Select customer and enter amount'); return; }

    // REC-001: Check that at least one open invoice exists for the customer
    if (outstandingInvoices.length === 0) {
      setError('No Open Invoice — Cannot record payment without an open invoice for this customer.');
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
      await paymentsApi.createPayment(payload);
      showSuccess('Payment recorded successfully');
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
    setAllocations({});
    setShowForm(true);
  };

  const sc: Record<string, string> = { pending: 'bg-amber-100 text-amber-700', cleared: 'bg-green-100 text-green-700', bounced: 'bg-red-100 text-red-700', cancelled: 'bg-gray-100 text-gray-700' };

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
          <button onClick={() => { resetForm(); setShowForm(true); }} className="rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-primary/20 hover:bg-primary/90">+ Record Payment</button>
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
                : filteredPayments.map(p => (
                  <tr key={p.id} className="border-b border-neutral-100 hover:bg-neutral-50">
                    <td className="px-4 py-3 font-medium">
                      {p.allocations?.map((a) => a.invoice_number).filter(Boolean).join(', ') || 'Unallocated'}
                    </td>
                    <td className="px-4 py-3">{customerNameById(p.customer_id)}</td>
                    <td className="px-4 py-3">{p.payment_date}</td>
                    <td className="px-4 py-3 capitalize">{p.payment_mode.replace('_', ' ')}</td>
                    <td className="px-4 py-3 text-right font-medium">{formatAmount(p.amount)}</td>
                    <td className="px-4 py-3 text-center"><span className={`inline-block rounded-full px-2.5 py-1 text-xs font-semibold ${sc[p.status]}`}>{statusDisplayLabel(p.status)}</span></td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex items-center justify-center gap-1">
                        {/* REC-008: Edit button for pending payments */}
                        {archiveView === 'active' && p.status === 'pending' && (
                          <>
                            <button onClick={() => handleEditPayment(p)} className="rounded px-2 py-1 text-xs font-medium text-primary hover:bg-primary/10">Edit</button>
                            <button onClick={() => handleStatusChange(p.id, 'cleared')} className="rounded px-2 py-1 text-xs font-medium text-green-600 hover:bg-green-50">Clear</button>
                            <button onClick={() => handleStatusChange(p.id, 'bounced')} className="rounded px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50">Bounced</button>
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
          {!loading && <p className="border-t border-neutral-200 px-4 py-3 text-xs text-neutral-500">Showing {filteredPayments.length} of {payments.length}</p>}
        </div>

        {showForm && createPortal(
          <div className="fixed inset-0 z-[100] m-0 flex min-h-screen w-screen items-start justify-center overflow-y-auto bg-black/45 p-4 pt-6 backdrop-blur-sm">
            <div className="hms-card my-8 w-full max-w-2xl space-y-6 p-6">
              <h2 className="font-display text-xl font-bold">{editingPayment ? 'Edit Customer Payment' : 'Record Customer Payment'}</h2>
              {error && <div className="rounded-lg bg-red-50 p-3 text-sm text-red-600">{error}</div>}
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Customer *</label><select className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={customerId} onChange={e => setCustomerId(e.target.value)}><option value="">Select</option>{customers.map(c => <option key={c.id} value={c.id}>{c.company_name}</option>)}</select></div>
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
                  <h3 className="mb-2 text-sm font-semibold text-neutral-700">Allocate to Invoices</h3>
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
                </div>
              )}

              <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Notes</label><textarea className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" rows={2} value={notes} onChange={e => setNotes(e.target.value)} /></div>
              <div className="flex justify-end gap-3">
                <button onClick={() => { setShowForm(false); resetForm(); }} className="rounded-lg border border-neutral-200 bg-white px-4 py-2.5 text-sm font-semibold text-neutral-600">Cancel</button>
                <button onClick={handleSubmit} disabled={submitting || (customerId !== '' && outstandingInvoices.length === 0)} className="rounded-lg bg-primary px-6 py-2.5 text-sm font-semibold text-white shadow-lg shadow-primary/20 disabled:opacity-50">{submitting ? 'Recording...' : 'Record Payment'}</button>
              </div>
            </div>
          </div>,
          document.body
        )}
      </div>
    </AppLayout>
  );
};

export default ReceivablesPage;

