import { RDNOverviewItem } from '../../types';

interface RDNOverviewTableProps {
  items: RDNOverviewItem[];
  loading: boolean;
  onSelect: (rdnId: string) => void;
}

const formatDate = (value: string) => {
  if (!value) return '-';
  const [year, month, day] = value.split('-');
  if (!year || !month || !day) return value;
  return `${day}-${month}-${year}`;
};

const formatAmount = (paise?: number | null) => {
  if (!paise) return 'Rs. 0.00';
  return `Rs. ${(paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
};

const statusStyles: Record<string, string> = {
  draft: 'bg-neutral-100 text-neutral-700',
  confirmed: 'bg-green-100 text-green-700',
  cancelled: 'bg-red-100 text-red-700',
};

export const RDNOverviewTable = ({ items, loading, onSelect }: RDNOverviewTableProps) => {
  return (
    <div className="hms-card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-neutral-200 bg-neutral-50">
              <th className="px-4 py-3 text-left font-semibold text-neutral-600">RDN Number</th>
              <th className="px-4 py-3 text-left font-semibold text-neutral-600">Customer</th>
              <th className="px-4 py-3 text-left font-semibold text-neutral-600">Invoice</th>
              <th className="px-4 py-3 text-left font-semibold text-neutral-600">Receipt Date</th>
              <th className="px-4 py-3 text-left font-semibold text-neutral-600">Product Code</th>
              <th className="px-4 py-3 text-left font-semibold text-neutral-600">Product</th>
              <th className="px-4 py-3 text-right font-semibold text-neutral-600">Quantity</th>
              <th className="px-4 py-3 text-right font-semibold text-neutral-600">MRP Value</th>
              <th className="px-4 py-3 text-center font-semibold text-neutral-600">Status</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={9} className="px-4 py-8 text-center text-neutral-500">Loading...</td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-4 py-8 text-center text-neutral-500">No RDNs found</td>
              </tr>
            ) : (
              items.map((row) => (
                <tr
                  key={`${row.rdn_id}-${row.product_id}`}
                  className="border-b border-neutral-100 hover:bg-neutral-50 cursor-pointer"
                  onClick={() => onSelect(row.rdn_id)}
                >
                  <td className="px-4 py-3 font-medium text-primary">{row.rdn_number}</td>
                  <td className="px-4 py-3">{row.customer_name}</td>
                  <td className="px-4 py-3">{row.invoice_number}</td>
                  <td className="px-4 py-3 text-neutral-500">{formatDate(row.receipt_date)}</td>
                  <td className="px-4 py-3">{row.product_code || '-'}</td>
                  <td className="px-4 py-3">{row.product_name || '-'}</td>
                  <td className="px-4 py-3 text-right font-medium">{row.return_quantity}</td>
                  <td className="px-4 py-3 text-right font-semibold text-amber-700 bg-amber-50">{formatAmount(row.mrp)}</td>
                  <td className="px-4 py-3 text-center">
                    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${statusStyles[row.status] || 'bg-neutral-100 text-neutral-700'}`}>
                      {row.status}
                    </span>
                  </td>
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
