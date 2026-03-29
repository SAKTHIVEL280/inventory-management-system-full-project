/**
 * Receivables Page (Customer Payments / Receipts)
 * Record payments from customers, allocate against invoices.
 */
import { useState, useEffect } from 'react';
import { AppLayout } from '../components/AppLayout';
import { paymentsApi, type Payment, type CreatePaymentPayload, type PaymentAllocationRequest } from '../api/payments';
import { salesApi, type SalesInvoice } from '../api/sales';
import { apiClient } from '../api/client';

interface CustomerOption { id: string; company_name: string; }

const ReceivablesPage = () => {
  const [payments, setPayments] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [customers, setCustomers] = useState<CustomerOption[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  // Outstanding invoices for selected customer
  const [outstandingInvoices, setOutstandingInvoices] = useState<SalesInvoice[]>([]);

  // Form
  const [customerId, setCustomerId] = useState('');
  const [paymentDate, setPaymentDate] = useState(new Date().toISOString().split('T')[0]);
  const [amount, setAmount] = useState(0);
  const [paymentMode, setPaymentMode] = useState('bank_transfer');
  const [referenceNumber, setReferenceNumber] = useState('');
  const [notes, setNotes] = useState('');
  const [allocations, setAllocations] = useState<Record<string, number>>({});

  const fetchPayments = async () => {
    try { setLoading(true); const res = await paymentsApi.listPayments({ party_type: 'customer' }); setPayments(res.data.items || []); } catch { /* */ } finally { setLoading(false); }
  };
  const fetchCustomers = async () => {
    try { const res = await apiClient.get('/api/v1/customers', { params: { page_size: 100 } }); setCustomers(res.data.items || []); } catch { /* */ }
  };

  useEffect(() => { fetchPayments(); fetchCustomers(); }, []);

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

  const resetForm = () => { setCustomerId(''); setPaymentDate(new Date().toISOString().split('T')[0]); setAmount(0); setPaymentMode('bank_transfer'); setReferenceNumber(''); setNotes(''); setAllocations({}); setError(''); };
  const formatAmount = (p: number) => `₹${(p / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;

  const handleSubmit = async () => {
    if (!customerId || amount <= 0) { setError('Select customer and enter amount'); return; }
    setSubmitting(true); setError('');
    try {
      const allocationList: PaymentAllocationRequest[] = Object.entries(allocations)
        .filter(([, amt]) => amt > 0)
        .map(([invoiceId, amt]) => ({ invoice_id: invoiceId, allocated_amount: amt }));

      const payload: CreatePaymentPayload = {
        payment_type: 'receipt', party_type: 'customer',
        customer_id: customerId, payment_date: paymentDate,
        amount, payment_mode: paymentMode,
        reference_number: referenceNumber || undefined,
        notes: notes || undefined,
        allocations: allocationList,
      };
      await paymentsApi.createPayment(payload);
      setShowForm(false); resetForm(); fetchPayments();
    } catch (err: unknown) { const m = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail; setError(typeof m === 'string' ? m : 'Failed'); } finally { setSubmitting(false); }
  };

  const handleStatusChange = async (id: string, status: string) => {
    try { await paymentsApi.updatePaymentStatus(id, status); fetchPayments(); } catch { alert('Failed'); }
  };

  const sc: Record<string, string> = { pending: 'bg-amber-100 text-amber-700', cleared: 'bg-green-100 text-green-700', bounced: 'bg-red-100 text-red-700', cancelled: 'bg-gray-100 text-gray-700' };

  return (
    <AppLayout title="Receivables (Customer Payments)">
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <p className="text-sm text-neutral-500">Record and manage payments received from customers</p>
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
                {loading ? <tr><td colSpan={6} className="px-4 py-8 text-center text-neutral-500">Loading...</td></tr>
                : payments.length === 0 ? <tr><td colSpan={6} className="px-4 py-8 text-center text-neutral-500">No payments recorded</td></tr>
                : payments.map(p => (
                  <tr key={p.id} className="border-b border-neutral-100 hover:bg-neutral-50">
                    <td className="px-4 py-3 font-medium">
                      {p.allocations?.map((a: any) => a.invoice_number).filter(Boolean).join(', ') || 'Unallocated'}
                    </td>
                    <td className="px-4 py-3">{customers.find(c => c.id === p.customer_id)?.company_name || '-'}</td>
                    <td className="px-4 py-3">{p.payment_date}</td>
                    <td className="px-4 py-3 capitalize">{p.payment_mode.replace('_', ' ')}</td>
                    <td className="px-4 py-3 text-right font-medium">{formatAmount(p.amount)}</td>
                    <td className="px-4 py-3 text-center"><span className={`inline-block rounded-full px-2.5 py-1 text-xs font-semibold ${sc[p.status]}`}>{p.status}</span></td>
                    <td className="px-4 py-3 text-center">
                      {p.status === 'pending' && (
                        <div className="flex items-center justify-center gap-1">
                          <button onClick={() => handleStatusChange(p.id, 'cleared')} className="rounded px-2 py-1 text-xs font-medium text-green-600 hover:bg-green-50">Clear</button>
                          <button onClick={() => handleStatusChange(p.id, 'bounced')} className="rounded px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50">Bounced</button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {showForm && (
          <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4 backdrop-blur-sm">
            <div className="hms-card my-8 w-full max-w-2xl space-y-6 p-6">
              <h2 className="font-display text-xl font-bold">Record Customer Payment</h2>
              {error && <div className="rounded-lg bg-red-50 p-3 text-sm text-red-600">{error}</div>}
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Customer *</label><select className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={customerId} onChange={e => setCustomerId(e.target.value)}><option value="">Select</option>{customers.map(c => <option key={c.id} value={c.id}>{c.company_name}</option>)}</select></div>
                <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Date *</label><input type="date" className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={paymentDate} onChange={e => setPaymentDate(e.target.value)} /></div>
                <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Amount (paise) *</label><input type="number" min="1" className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={amount} onChange={e => setAmount(parseInt(e.target.value) || 0)} /></div>
                <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Mode</label><select className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={paymentMode} onChange={e => setPaymentMode(e.target.value)}><option value="cash">Cash</option><option value="bank_transfer">Bank Transfer</option><option value="cheque">Cheque</option><option value="upi">UPI</option><option value="card">Card</option></select></div>
                <div className="md:col-span-2"><label className="mb-1 block text-sm font-semibold text-neutral-700">Reference #</label><input type="text" className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={referenceNumber} onChange={e => setReferenceNumber(e.target.value)} /></div>
              </div>

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
                            <td className="px-3 py-2"><input type="number" min="0" max={inv.amount_due} className="w-full rounded border px-2 py-1.5 text-right text-sm" value={allocations[inv.id] || 0} onChange={e => setAllocations({ ...allocations, [inv.id]: parseInt(e.target.value) || 0 })} /></td>
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
                <button onClick={handleSubmit} disabled={submitting} className="rounded-lg bg-primary px-6 py-2.5 text-sm font-semibold text-white shadow-lg shadow-primary/20 disabled:opacity-50">{submitting ? 'Recording...' : 'Record Payment'}</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
};

export default ReceivablesPage;
