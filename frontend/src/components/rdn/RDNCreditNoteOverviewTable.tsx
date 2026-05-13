import { RDNCreditNoteOverviewItem } from '../../types';

interface RDNCreditNoteOverviewTableProps {
  items: RDNCreditNoteOverviewItem[];
  loading: boolean;
  onSelect: (creditNoteId: string) => void;
}

const formatAmount = (paise?: number | null) => {
  if (!paise) return 'Rs. 0.00';
  return `Rs. ${(paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
};

export const RDNCreditNoteOverviewTable = ({ items, loading, onSelect }: RDNCreditNoteOverviewTableProps) => {
  return (
    <div className="hms-card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-neutral-200 bg-neutral-50">
              <th className="px-4 py-3 text-left font-semibold text-neutral-600">RDN Number</th>
              <th className="px-4 py-3 text-left font-semibold text-neutral-600">Sales Invoice</th>
              <th className="px-4 py-3 text-left font-semibold text-neutral-600">Item / Product</th>
              <th className="px-4 py-3 text-left font-semibold text-neutral-600">Customer</th>
              <th className="px-4 py-3 text-right font-semibold text-neutral-600">MRP</th>
              <th className="px-4 py-3 text-right font-semibold text-neutral-600">GST %</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-neutral-500">Loading...</td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-neutral-500">No credit notes found</td>
              </tr>
            ) : (
              items.map((row) => (
                <tr
                  key={`${row.credit_note_id}-${row.product_id}`}
                  className="border-b border-neutral-100 hover:bg-neutral-50 cursor-pointer"
                  onClick={() => onSelect(row.credit_note_id)}
                >
                  <td className="px-4 py-3 font-medium text-primary">{row.credit_note_number}</td>
                  <td className="px-4 py-3">{row.invoice_number}</td>
                  <td className="px-4 py-3">{row.product_name || row.product_code || row.product_id}</td>
                  <td className="px-4 py-3">{row.customer_name}</td>
                  <td className="px-4 py-3 text-right font-semibold text-amber-700 bg-amber-50">{formatAmount(row.mrp)}</td>
                  <td className="px-4 py-3 text-right">{row.gst_rate}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {!loading && (
        <p className="border-t border-neutral-200 px-4 py-3 text-xs text-neutral-500">
          Showing {items.length} rows
        </p>
      )}
    </div>
  );
};
