/**
 * Payables Page (Supplier Payments)
 * Record payments to suppliers, allocate against GRNs.
 *
 * Fixes applied:
 * - PAY-001: GRN Number displayed in list
 * - PAY-002: GRN Value displayed in list
 * - PAY-003: PO Number displayed in list
 * - PAY-004: Advance Payment button when no GRN available
 * - PAY-005: Button order → Advance Payment → Record Payment → Cancel
 * - PAY-006: Total Record Payments cannot exceed GRN Value
 * - PAY-007: Edit option after Recording payment (before Clear/Bounce)
 */
import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { AppLayout } from '../components/AppLayout';
import { paymentsApi, type Payment, type CreatePaymentPayload, type PaymentAllocationRequest } from '../api/payments';
import { purchaseApi, type GoodsReceiptNote } from '../api/purchase';
import { apiClient } from '../api/client';
import { todayLocalDateInputValue } from '../utils/date';
import { showError, showSuccess, confirmWithToast } from '../utils/toastHelper';

interface SupplierOption { id: string; company_name: string; }

const PayablesPage = () => {
  const [payments, setPayments] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [suppliers, setSuppliers] = useState<SupplierOption[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [modeFilter, setModeFilter] = useState('');
  const [archiveView, setArchiveView] = useState<'active' | 'archived'>('active');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  // PAY-001/002/003: Outstanding GRNs for selected supplier
  const [outstandingGRNs, setOutstandingGRNs] = useState<GoodsReceiptNote[]>([]);

  // PAY-004: Advance payment mode
  const [isAdvancePayment, setIsAdvancePayment] = useState(false);

  // Edit mode
  const [editingPayment, setEditingPayment] = useState<Payment | null>(null);

  const [supplierId, setSupplierId] = useState('');
  const [paymentDate, setPaymentDate] = useState(todayLocalDateInputValue());
  const [amount, setAmount] = useState(0);
  const [paymentMode, setPaymentMode] = useState('bank_transfer');
  const [referenceNumber, setReferenceNumber] = useState('');
  const [notes, setNotes] = useState('');
  const [allocations, setAllocations] = useState<Record<string, number>>({});

  const fetchPayments = async () => {
    try {
      setLoading(true);
      const res = await paymentsApi.listPayments({ party_type: 'supplier', archived_only: archiveView === 'archived' });
      setPayments(res.data.items || []);
    } catch {
      /* */
    } finally {
      setLoading(false);
    }
  };
  const fetchSuppliers = async () => {
    try { const res = await apiClient.get('/api/v1/suppliers', { params: { page_size: 100 } }); setSuppliers(res.data.items || []); } catch { /* */ }
  };

  // eslint-disable-next-line react-hooks/exhaustive-deps -- fetchPayments should run when archiveView changes
  useEffect(() => { fetchPayments(); }, [archiveView]);
  useEffect(() => { fetchSuppliers(); }, []);

  // When supplier changes, fetch their confirmed GRNs
  useEffect(() => {
    if (!supplierId) { setOutstandingGRNs([]); return; }
    (async () => {
      try {
        const res = await purchaseApi.listGRNs('confirmed', 1, 100, { supplier_id: supplierId });
        setOutstandingGRNs(res.data.items || []);
      } catch { setOutstandingGRNs([]); }
    })();
  }, [supplierId]);

  const resetForm = () => { setSupplierId(''); setPaymentDate(todayLocalDateInputValue()); setAmount(0); setPaymentMode('bank_transfer'); setReferenceNumber(''); setNotes(''); setAllocations({}); setError(''); setIsAdvancePayment(false); setEditingPayment(null); };
  const paiseToRupees = (paise: number) => (Number.isFinite(paise) ? paise / 100 : 0);
  const rupeesToPaise = (value: string | number) => {
    const num = typeof value === 'number' ? value : parseFloat(value);
    return Number.isFinite(num) ? Math.round(num * 100) : 0;
  };
  const formatAmount = (p: number) => `₹${(p / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
  const supplierNameById = (id?: string | null) => suppliers.find((s) => s.id === id)?.company_name || '-';

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

  const filteredPayments = payments.filter((p) => {
    const term = searchQuery.trim().toLowerCase();
    const allocationRefs = p.allocations?.map((a) => a.po_number || a.grn_number).filter(Boolean).join(' ') || '';
    const matchesSearch =
      !term ||
      supplierNameById(p.supplier_id).toLowerCase().includes(term) ||
      p.payment_date.toLowerCase().includes(term) ||
      p.status.toLowerCase().includes(term) ||
      p.payment_mode.toLowerCase().includes(term) ||
      allocationRefs.toLowerCase().includes(term) ||
      (p.reference_number || '').toLowerCase().includes(term);
    const matchesStatus = !statusFilter || p.status === statusFilter;
    const matchesMode = !modeFilter || p.payment_mode === modeFilter;
    const matchesFrom = !dateFrom || p.payment_date >= dateFrom;
    const matchesTo = !dateTo || p.payment_date <= dateTo;
    return matchesSearch && matchesStatus && matchesMode && matchesFrom && matchesTo;
  });

  const handleSubmit = async () => {
    if (!supplierId || amount <= 0) { setError('Select supplier and enter amount'); return; }

    // PAY-006: Validate total allocations don't exceed GRN values
    if (!isAdvancePayment) {
      for (const [grnId, allocAmt] of Object.entries(allocations)) {
        if (allocAmt > 0) {
          const grn = outstandingGRNs.find(g => g.id === grnId);
          if (grn && allocAmt > grn.total_amount) {
            setError(`Allocated amount for GRN ${grn.grn_number} exceeds its value of ${formatAmount(grn.total_amount)}`);
            return;
          }
        }
      }
    }

    setSubmitting(true); setError('');
    try {
      const allocationList: PaymentAllocationRequest[] = Object.entries(allocations)
        .filter(([, amt]) => amt > 0)
        .map(([grnId, amt]) => ({ purchase_grn_id: grnId, allocated_amount: amt }));

      const payload: CreatePaymentPayload = {
        payment_type: 'payment', party_type: 'supplier',
        supplier_id: supplierId, payment_date: paymentDate,
        amount: amount, payment_mode: paymentMode,
        reference_number: referenceNumber || undefined,
        notes: isAdvancePayment ? `[ADVANCE PAYMENT] ${notes || ''}`.trim() : (notes || undefined),
        allocations: allocationList,
      };
      await paymentsApi.createPayment(payload);
      showSuccess(isAdvancePayment ? 'Advance payment recorded' : 'Payment recorded successfully');
      setShowForm(false); resetForm(); fetchPayments();
    } catch (err: unknown) { const m = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail; setError(typeof m === 'string' ? m : 'Failed'); } finally { setSubmitting(false); }
  };

  const handleStatusChange = async (id: string, newStatus: string) => {
    const confirmMsg = newStatus === 'bounced'
      ? 'Are you sure you want to mark this payment as bounced?'
      : newStatus === 'cleared'
        ? 'Are you sure you want to confirm payment cleared?'
        : `Change status to ${newStatus}?`;
    const confirmType = newStatus === 'bounced' ? 'danger' : 'warning';

    const confirmed = await confirmWithToast(confirmMsg, { type: confirmType as 'confirm' | 'warning' | 'danger' });
    if (!confirmed) return;

    try {
      await paymentsApi.updatePaymentStatus(id, newStatus);
      showSuccess('Payment status updated');
      fetchPayments();
    } catch {
      showError('Failed to update payment status');
    }
  };

  const handleArchiveToggle = async (id: string, archived: boolean) => {
    try {
      if (archived) {
        await paymentsApi.restorePayment(id);
      } else {
        await paymentsApi.archivePayment(id);
      }
      showSuccess(archived ? 'Payment restored' : 'Payment archived');
      fetchPayments();
    } catch {
      showError(archived ? 'Restore failed' : 'Archive failed');
    }
  };

  // PAY-007: Open edit form
  const handleEditPayment = (p: Payment) => {
    setEditingPayment(p);
    setSupplierId(p.supplier_id || '');
    setPaymentDate(p.payment_date);
    setAmount(p.amount);
    setPaymentMode(p.payment_mode);
    setReferenceNumber(p.reference_number || '');
    setNotes('');
    setAllocations({});
    setIsAdvancePayment(false);
    setShowForm(true);
  };

  const sc: Record<string, string> = { pending: 'bg-amber-100 text-amber-700', cleared: 'bg-green-100 text-green-700', bounced: 'bg-red-100 text-red-700', cancelled: 'bg-gray-100 text-gray-700' };

  return (
    <AppLayout title="Payables (Supplier Payments)">
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <input
              type="text"
              className="w-64 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm"
              placeholder="Search supplier, PO/GRN, ref #, status..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <select className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">All Statuses</option>
              <option value="pending">Pending</option>
              <option value="cleared">Cleared</option>
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
          {/* PAY-005: Advance Payment → Record Payment → Cancel order */}
          <div className="flex items-center gap-2">
            <button onClick={() => { resetForm(); setIsAdvancePayment(true); setShowForm(true); }} className="rounded-lg border-2 border-amber-400 bg-amber-50 px-4 py-2.5 text-sm font-semibold text-amber-700 hover:bg-amber-100">Advance Payment</button>
            <button onClick={() => { resetForm(); setShowForm(true); }} className="rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-primary/20 hover:bg-primary/90">+ Record Payment</button>
          </div>
        </div>

        <div className="hms-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-neutral-200 bg-neutral-50">
                {/* PAY-001/003: Show GRN # and PO # columns */}
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">GRN #</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">PO #</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Supplier</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Date</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Mode</th>
                {/* PAY-002: GRN Value column */}
                <th className="px-4 py-3 text-right font-semibold text-neutral-600">GRN Value</th>
                <th className="px-4 py-3 text-right font-semibold text-neutral-600">Paid Amount</th>
                <th className="px-4 py-3 text-center font-semibold text-neutral-600">Status</th>
                <th className="px-4 py-3 text-center font-semibold text-neutral-600">Actions</th>
              </tr></thead>
              <tbody>
                {loading ? <tr><td colSpan={9} className="px-4 py-8 text-center text-neutral-500">Loading...</td></tr>
                : filteredPayments.length === 0 ? <tr><td colSpan={9} className="px-4 py-8 text-center text-neutral-500">No payments recorded</td></tr>
                : filteredPayments.map(p => (
                  <tr key={p.id} className="border-b border-neutral-100 hover:bg-neutral-50">
                    {/* PAY-001: GRN Number */}
                    <td className="px-4 py-3 font-medium text-xs">
                      {p.allocations?.map((a) => a.grn_number).filter(Boolean).join(', ') || (p.notes?.includes('[ADVANCE PAYMENT]') ? <span className="text-amber-600 font-semibold">Advance</span> : '—')}
                    </td>
                    {/* PAY-003: PO Number */}
                    <td className="px-4 py-3 text-xs">
                      {p.allocations?.map((a) => a.po_number).filter(Boolean).join(', ') || '—'}
                    </td>
                    <td className="px-4 py-3">{supplierNameById(p.supplier_id)}</td>
                    <td className="px-4 py-3">{p.payment_date}</td>
                    <td className="px-4 py-3 capitalize">{p.payment_mode.replace('_', ' ')}</td>
                    {/* PAY-002: GRN Value */}
                    <td className="px-4 py-3 text-right text-neutral-500">
                      {p.allocations?.length && p.allocations.length > 0
                        ? p.allocations.map((a) => a.grn_total_amount ? formatAmount(a.grn_total_amount) : '').filter(Boolean).join(', ') || '—'
                        : '—'}
                    </td>
                    <td className="px-4 py-3 text-right font-medium">{formatAmount(p.amount)}</td>
                    <td className="px-4 py-3 text-center"><span className={`inline-block rounded-full px-2.5 py-1 text-xs font-semibold ${sc[p.status]}`}>{p.status}</span></td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex items-center justify-center gap-1">
                        {archiveView === 'active' && p.status === 'pending' && (
                          <>
                            {/* PAY-007: Edit button */}
                            <button onClick={() => handleEditPayment(p)} className="rounded px-2 py-1 text-xs font-medium text-primary hover:bg-primary/10">Edit</button>
                            <button onClick={() => handleStatusChange(p.id, 'cleared')} className="rounded px-2 py-1 text-xs font-medium text-green-600 hover:bg-green-50">Clear</button>
                            <button onClick={() => handleStatusChange(p.id, 'cancelled')} className="rounded px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50">Cancel</button>
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
              <h2 className="font-display text-xl font-bold">
                {isAdvancePayment ? 'Advance Supplier Payment' : editingPayment ? 'Edit Supplier Payment' : 'Record Supplier Payment'}
              </h2>
              {isAdvancePayment && (
                <div className="rounded-lg bg-amber-50 border border-amber-200 p-3 text-sm text-amber-700">
                  <strong>Advance Payment</strong> — This payment is not linked to any GRN. It will be recorded as an advance.
                </div>
              )}
              {error && <div className="rounded-lg bg-red-50 p-3 text-sm text-red-600">{error}</div>}
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Supplier *</label><select className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={supplierId} onChange={e => setSupplierId(e.target.value)}><option value="">Select</option>{suppliers.map(s => <option key={s.id} value={s.id}>{s.company_name}</option>)}</select></div>
                <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Date *</label><input type="date" className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={paymentDate} onChange={e => setPaymentDate(e.target.value)} /></div>
                <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Amount (₹) *</label><input type="number" step="0.01" min="0.01" className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={amount > 0 ? paiseToRupees(amount) : ''} onChange={e => setAmount(rupeesToPaise(e.target.value))} /></div>
                <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Mode</label><select className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={paymentMode} onChange={e => setPaymentMode(e.target.value)}><option value="cash">Cash</option><option value="bank_transfer">Bank Transfer</option><option value="cheque">Cheque</option><option value="upi">UPI</option><option value="card">Card</option></select></div>
                <div className="md:col-span-2"><label className="mb-1 block text-sm font-semibold text-neutral-700">Reference #</label><input type="text" className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={referenceNumber} onChange={e => setReferenceNumber(e.target.value)} /></div>
              </div>

              {/* PAY-001/002/003: Show GRN allocations when not advance payment */}
              {!isAdvancePayment && outstandingGRNs.length > 0 && (
                <div>
                  <h3 className="mb-2 text-sm font-semibold text-neutral-700">Allocate to GRNs</h3>
                  <div className="rounded-lg border border-neutral-200">
                    <table className="w-full text-sm">
                      <thead><tr className="bg-neutral-50">
                        <th className="px-3 py-2 text-left">GRN #</th>
                        <th className="px-3 py-2 text-left">PO #</th>
                        <th className="px-3 py-2 text-right">GRN Value</th>
                        <th className="px-3 py-2 text-right w-32">Allocate</th>
                      </tr></thead>
                      <tbody>
                        {outstandingGRNs.map(grn => (
                          <tr key={grn.id} className="border-t border-neutral-100">
                            <td className="px-3 py-2 font-medium">{grn.grn_number}</td>
                            <td className="px-3 py-2 text-xs">{grn.po_number || '—'}</td>
                            <td className="px-3 py-2 text-right">{formatAmount(grn.total_amount)}</td>
                            <td className="px-3 py-2"><input type="number" step="0.01" min="0" max={paiseToRupees(grn.total_amount)} className="w-full rounded border px-2 py-1.5 text-right text-sm" value={allocations[grn.id] ? paiseToRupees(allocations[grn.id]) : ''} onChange={e => {
                              const newVal = rupeesToPaise(e.target.value);
                              // PAY-006: Clamp allocation to GRN value
                              const clamped = Math.min(newVal, grn.total_amount);
                              setAllocations({ ...allocations, [grn.id]: clamped });
                            }} /></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {!isAdvancePayment && supplierId && outstandingGRNs.length === 0 && (
                <div className="rounded-lg bg-amber-50 border border-amber-200 p-3 text-sm text-amber-700">
                  No confirmed GRNs found for this supplier. Use <strong>Advance Payment</strong> if you need to pay without a GRN.
                </div>
              )}

              <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Notes</label><textarea className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" rows={2} value={notes} onChange={e => setNotes(e.target.value)} /></div>
              <div className="flex justify-end gap-3">
                <button onClick={() => { setShowForm(false); resetForm(); }} className="rounded-lg border border-neutral-200 bg-white px-4 py-2.5 text-sm font-semibold text-neutral-600">Cancel</button>
                <button onClick={handleSubmit} disabled={submitting} className="rounded-lg bg-primary px-6 py-2.5 text-sm font-semibold text-white shadow-lg shadow-primary/20 disabled:opacity-50">{submitting ? 'Recording...' : (isAdvancePayment ? 'Record Advance' : 'Record Payment')}</button>
              </div>
            </div>
          </div>,
          document.body
        )}
      </div>
    </AppLayout>
  );
};

export default PayablesPage;
