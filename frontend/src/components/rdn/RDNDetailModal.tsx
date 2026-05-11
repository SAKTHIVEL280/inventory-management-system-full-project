import { createPortal } from 'react-dom';
import { RDN, RDNItem } from '../../types';

interface RDNDetailModalProps {
  open: boolean;
  rdn: RDN | null;
  items: RDNItem[];
  onClose: () => void;
  onConfirm: () => void;
  onCancel: () => void;
  onEdit: () => void;
  canConfirm?: boolean;
}

const formatDate = (value?: string | null) => {
  if (!value) return '-';
  const [year, month, day] = value.split('-');
  if (!year || !month || !day) return value;
  return `${day}-${month}-${year}`;
};

const formatAmount = (paise?: number | null) => {
  if (!paise) return 'Rs. 0.00';
  return `Rs. ${(paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
};

export const RDNDetailModal = ({ open, rdn, items, onClose, onConfirm, onCancel, onEdit, canConfirm = false }: RDNDetailModalProps) => {
  if (!open || !rdn) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4">
      <div className="w-full max-w-5xl rounded-xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-neutral-200 px-6 py-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-neutral-500">Return Delivery Note</p>
            <h2 className="text-lg font-bold text-neutral-900">{rdn.rdn_number}</h2>
          </div>
          <button onClick={onClose} className="text-neutral-500 hover:text-neutral-700">X</button>
        </div>

        <div className="grid gap-4 px-6 py-4 md:grid-cols-2">
          <div className="rounded-lg border border-neutral-200 p-3">
            <p className="text-xs uppercase text-neutral-400">Customer Delivery</p>
            <p className="text-sm font-semibold">{rdn.customer_delivery_number || '-'}</p>
            <p className="text-xs text-neutral-500">Delivery Date: {formatDate(rdn.customer_delivery_date)}</p>
          </div>
          <div className="rounded-lg border border-neutral-200 p-3">
            <p className="text-xs uppercase text-neutral-400">Receipt Date</p>
            <p className="text-sm font-semibold">{formatDate(rdn.receipt_date)}</p>
            <p className="text-xs text-neutral-500">Status: {rdn.status}</p>
          </div>
        </div>

        <div className="px-6 pb-4">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-neutral-200 bg-neutral-50">
                  <th className="px-3 py-2 text-left font-semibold text-neutral-600">Product</th>
                  <th className="px-3 py-2 text-left font-semibold text-neutral-600">Batch</th>
                  <th className="px-3 py-2 text-left font-semibold text-neutral-600">MFG</th>
                  <th className="px-3 py-2 text-left font-semibold text-neutral-600">EXP</th>
                  <th className="px-3 py-2 text-right font-semibold text-neutral-600">Invoice Qty</th>
                  <th className="px-3 py-2 text-right font-semibold text-neutral-600">Return Qty</th>
                  <th className="px-3 py-2 text-right font-semibold text-neutral-600">MRP</th>
                  <th className="px-3 py-2 text-left font-semibold text-neutral-600">Reason</th>
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
                      <td className="px-3 py-2">{item.product_name || item.product_code || item.product_id}</td>
                      <td className="px-3 py-2">{item.batch_no}</td>
                      <td className="px-3 py-2 text-neutral-500">{formatDate(item.manufacture_date)}</td>
                      <td className="px-3 py-2 text-neutral-500">{formatDate(item.expiry_date)}</td>
                      <td className="px-3 py-2 text-right">{item.invoice_quantity}</td>
                      <td className="px-3 py-2 text-right font-semibold">{item.return_quantity}</td>
                      <td className="px-3 py-2 text-right text-amber-700 font-semibold">{formatAmount(item.mrp)}</td>
                      <td className="px-3 py-2">{item.reason_label}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-end gap-3 border-t border-neutral-200 px-6 py-4">
          <button onClick={onClose} className="rounded-lg border border-neutral-200 px-4 py-2 text-sm font-semibold text-neutral-600">Close</button>
          {rdn.status === 'draft' && (
            <>
              <button onClick={onEdit} className="rounded-lg border border-neutral-200 px-4 py-2 text-sm font-semibold text-neutral-600">Edit</button>
              <button onClick={onCancel} className="rounded-lg border border-red-200 px-4 py-2 text-sm font-semibold text-red-600">Cancel</button>
              {canConfirm && (
                <button onClick={onConfirm} className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white">Confirm</button>
              )}
            </>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
};
