import { createPortal } from 'react-dom';
import type { RDNCreditNote, RDNCreditNoteItem } from '../../types';

interface RDNCreditNoteDetailModalProps {
  open: boolean;
  creditNote: RDNCreditNote | null;
  items: RDNCreditNoteItem[];
  onClose: () => void;
}

const formatDate = (value?: string | null) => {
  if (!value) return '-';
  const [year, month, day] = value.split('-');
  if (!year || !month || !day) return value;
  return `${day}-${month}-${year}`;
};

const formatDateTime = (value?: string | null) => {
  if (!value) return '-';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  });
};

const formatAmount = (paise?: number | null) => {
  if (!paise) return 'Rs. 0.00';
  return `Rs. ${(paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
};

const roundToNearestFivePaise = (value: number) => {
  if (!Number.isFinite(value)) return 0;
  const normalized = Math.round(value);
  const step = 500;
  if (normalized >= 0) return Math.floor(normalized / step) * step;
  return -Math.floor(Math.abs(normalized) / step) * step;
};

export const RDNCreditNoteDetailModal = ({ open, creditNote, items, onClose }: RDNCreditNoteDetailModalProps) => {
  if (!open || !creditNote) return null;

  const exactTotalPaise = Number(creditNote.total_taxable_amount || 0) + Number(creditNote.total_gst || 0);
  const roundedTotalPaise = roundToNearestFivePaise(exactTotalPaise);
  const roundOffPaise = roundedTotalPaise - exactTotalPaise;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4">
      <div className="w-full max-w-6xl rounded-xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-neutral-200 px-6 py-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-neutral-500">Return Delivery - Credit Note</p>
            <h2 className="text-lg font-bold text-neutral-900">{creditNote.credit_note_number}</h2>
          </div>
          <button onClick={onClose} className="text-neutral-500 hover:text-neutral-700">X</button>
        </div>

        <div className="grid gap-4 px-6 py-4 md:grid-cols-2">
          <div className="rounded-lg border border-neutral-200 p-3">
            <p className="text-xs uppercase text-neutral-400">RDN Created Date</p>
            <p className="text-sm font-semibold">{formatDateTime(creditNote.rdn_created_at)}</p>
            <p className="text-xs text-neutral-500">Credit Note Date: {formatDate(creditNote.credit_note_date)}</p>
          </div>
          <div className="rounded-lg border border-neutral-200 p-3">
            <p className="text-xs uppercase text-neutral-400">Sales Invoice</p>
            <p className="text-sm font-semibold">{creditNote.invoice_number || '-'}</p>
            <p className="text-xs text-neutral-500">Invoice Date: {formatDate(creditNote.invoice_date)}</p>
          </div>
          <div className="rounded-lg border border-neutral-200 p-3">
            <p className="text-xs uppercase text-neutral-400">Customer</p>
            <p className="text-sm font-semibold">{creditNote.customer_name || '-'}</p>
            <p className="text-xs text-neutral-500">Status: {creditNote.status}</p>
          </div>
          <div className="rounded-lg border border-neutral-200 p-3">
            <p className="text-xs uppercase text-neutral-400">Total Amount</p>
            <p className="text-sm font-semibold text-amber-700">{formatAmount(roundedTotalPaise)}</p>
            <p className="text-xs text-neutral-500">GST: {formatAmount(creditNote.total_gst)}</p>
            <p className="text-xs text-neutral-500">Round Off: {formatAmount(roundOffPaise)}</p>
            <p className="text-xs font-semibold text-neutral-700">Grand Total: {formatAmount(roundedTotalPaise)}</p>
          </div>
        </div>

        <div className="px-6 pb-4">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-neutral-200 bg-neutral-50">
                  <th className="px-3 py-2 text-left font-semibold text-neutral-600">Product</th>
                  <th className="px-3 py-2 text-right font-semibold text-neutral-600">Return Qty</th>
                  <th className="px-3 py-2 text-right font-semibold text-neutral-600">MRP</th>
                  <th className="px-3 py-2 text-right font-semibold text-neutral-600">Discount</th>
                  <th className="px-3 py-2 text-right font-semibold text-neutral-600">CGST</th>
                  <th className="px-3 py-2 text-right font-semibold text-neutral-600">SGST</th>
                  <th className="px-3 py-2 text-right font-semibold text-neutral-600">IGST</th>
                  <th className="px-3 py-2 text-right font-semibold text-neutral-600">Total</th>
                </tr>
              </thead>
              <tbody>
                {items.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-3 py-6 text-center text-neutral-400">No items</td>
                  </tr>
                ) : (
                  items.map((item) => (
                    <tr key={item.id} className="border-b border-neutral-100">
                      <td className="px-3 py-2">
                        <div className="font-medium">{item.product_name || item.product_code || item.product_id}</div>
                        <div className="text-xs text-neutral-500">GST {item.gst_rate}%</div>
                      </td>
                      <td className="px-3 py-2 text-right">{item.return_quantity}</td>
                      <td className="px-3 py-2 text-right">{formatAmount(item.mrp)}</td>
                      <td className="px-3 py-2 text-right">{formatAmount(item.discount_amount)}</td>
                      <td className="px-3 py-2 text-right">{formatAmount(item.cgst_amount)}</td>
                      <td className="px-3 py-2 text-right">{formatAmount(item.sgst_amount)}</td>
                      <td className="px-3 py-2 text-right">{formatAmount(item.igst_amount)}</td>
                      <td className="px-3 py-2 text-right font-semibold">{formatAmount(item.total_amount)}</td>
                    </tr>
                  ))
                )}
              </tbody>
              {items.length > 0 && (
                <tfoot>
                  <tr className="border-t-2 bg-neutral-50">
                    <td colSpan={7} className="px-3 py-2 text-right font-semibold">Total:</td>
                    <td className="px-3 py-2 text-right font-medium">{formatAmount(exactTotalPaise)}</td>
                  </tr>
                  {roundOffPaise !== 0 && (
                    <tr className="bg-neutral-50">
                      <td colSpan={7} className="px-3 py-2 text-right font-semibold">Round Off:</td>
                      <td className="px-3 py-2 text-right font-medium">{formatAmount(roundOffPaise)}</td>
                    </tr>
                  )}
                  <tr className="bg-neutral-50">
                    <td colSpan={7} className="px-3 py-2 text-right font-semibold">Grand Total:</td>
                    <td className="px-3 py-2 text-right font-bold text-primary">{formatAmount(roundedTotalPaise)}</td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        </div>

        <div className="flex items-center justify-end border-t border-neutral-200 px-6 py-4">
          <button onClick={onClose} className="rounded-lg border border-neutral-200 px-4 py-2 text-sm font-semibold text-neutral-600">Close</button>
        </div>
      </div>
    </div>,
    document.body
  );
};
