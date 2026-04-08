import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { toast } from 'sonner';

import { AppLayout } from '../components/AppLayout';
import { stockApi, type InventoryCountDifferenceResponse } from '../api/stock';

const InventoryCountDifferencePage = () => {
  const [countNumber, setCountNumber] = useState('');
  const [result, setResult] = useState<InventoryCountDifferenceResponse | null>(null);

  const differenceMutation = useMutation({
    mutationFn: (number: string) => stockApi.getInventoryCountDifference(number),
    onSuccess: (data) => {
      setResult(data);
      if (data.items.length === 0) {
        toast.info('No count items found for this inventory count number.');
      }
    },
    onError: (error: unknown) => {
      const message = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(message || 'Failed to fetch inventory count difference');
      setResult(null);
    },
  });

  const searchDifference = () => {
    const token = countNumber.trim();
    if (!token) {
      toast.error('Please enter Inventory Count Number');
      return;
    }
    differenceMutation.mutate(token);
  };

  return (
    <AppLayout title="Inventory Count Difference (Admin)">
      <div className="space-y-6">
        <div className="hms-card p-5">
          <h2 className="font-display text-lg font-semibold text-neutral-900">Find Inventory Count Difference</h2>
          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="sm:w-80">
              <label className="hms-label">Inventory Count Number</label>
              <input
                type="text"
                className="hms-input"
                value={countNumber}
                onChange={(e) => setCountNumber(e.target.value.toUpperCase())}
                placeholder="INV-APR-001"
              />
            </div>
            <button type="button" className="hms-button-primary" onClick={searchDifference}>
              {differenceMutation.isPending ? 'Loading...' : 'Show Difference'}
            </button>
          </div>
        </div>

        {result && (
          <>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
              <div className="hms-card p-4">
                <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Count Number</p>
                <p className="mt-2 text-base font-semibold text-neutral-900">{result.count_number}</p>
              </div>
              <div className="hms-card p-4">
                <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Count Date</p>
                <p className="mt-2 text-base font-semibold text-neutral-900">{result.count_date}</p>
              </div>
              <div className="hms-card p-4">
                <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Count Performed By</p>
                <p className="mt-2 text-base font-semibold text-neutral-900">{result.count_performed_by}</p>
              </div>
              <div className="hms-card p-4">
                <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Total Items</p>
                <p className="mt-2 text-base font-semibold text-neutral-900">{result.total_items}</p>
              </div>
            </div>

            <div className="hms-card overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-neutral-200 bg-neutral-50">
                      <th className="px-4 py-3 text-left font-semibold text-neutral-600">S.No</th>
                      <th className="px-4 py-3 text-left font-semibold text-neutral-600">Product ID</th>
                      <th className="px-4 py-3 text-left font-semibold text-neutral-600">Product</th>
                      <th className="px-4 py-3 text-left font-semibold text-neutral-600">Batch</th>
                      <th className="px-4 py-3 text-left font-semibold text-neutral-600">Mfg</th>
                      <th className="px-4 py-3 text-left font-semibold text-neutral-600">Exp</th>
                      <th className="px-4 py-3 text-right font-semibold text-neutral-600">Count Qty</th>
                      <th className="px-4 py-3 text-right font-semibold text-neutral-600">Existing Stock</th>
                      <th className="px-4 py-3 text-right font-semibold text-neutral-600">Difference</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.items.length === 0 ? (
                      <tr>
                        <td colSpan={9} className="px-4 py-8 text-center text-neutral-500">No rows found</td>
                      </tr>
                    ) : (
                      result.items.map((item, index) => (
                        <tr key={`${item.product_id}-${item.serial_number}-${index}`} className="border-b border-neutral-100">
                          <td className="px-4 py-3">{item.serial_number}</td>
                          <td className="px-4 py-3 text-xs text-neutral-600">{item.product_id}</td>
                          <td className="px-4 py-3">
                            <div className="font-medium text-neutral-900">{item.product_name || '—'}</div>
                            <div className="text-xs text-neutral-500">{item.product_code || ''}</div>
                            <div className="text-xs text-neutral-500">{item.product_description || ''}</div>
                          </td>
                          <td className="px-4 py-3">{item.batch_no || '—'}</td>
                          <td className="px-4 py-3">{item.manufacture_date || '—'}</td>
                          <td className="px-4 py-3">{item.expiry_date || '—'}</td>
                          <td className="px-4 py-3 text-right">{item.counted_quantity}</td>
                          <td className="px-4 py-3 text-right">{item.existing_stock}</td>
                          <td className={`px-4 py-3 text-right font-semibold ${item.difference === 0 ? 'text-neutral-700' : item.difference > 0 ? 'text-green-700' : 'text-red-700'}`}>
                            {item.difference}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </div>
    </AppLayout>
  );
};

export default InventoryCountDifferencePage;
