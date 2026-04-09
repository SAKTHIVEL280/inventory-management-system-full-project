import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';

import { AppLayout } from '../components/AppLayout';
import { stockApi, type InventoryCountDifferenceResponse } from '../api/stock';

const InventoryCountDifferencePage = () => {
  const [countNumber, setCountNumber] = useState('');
  const [isSuggestionsOpen, setIsSuggestionsOpen] = useState(false);
  const [hasTypedSinceFocus, setHasTypedSinceFocus] = useState(false);
  const searchToken = countNumber.trim().toUpperCase();

  const {
    data: allDifferences = [],
    isLoading: isAllDifferencesLoading,
    isError: isAllDifferencesError,
  } = useQuery({
    queryKey: ['inventory-count-differences-all'],
    queryFn: () => stockApi.getAllInventoryCountDifferences(300),
    staleTime: 30_000,
  });

  const { data: suggestionsResponse } = useQuery({
    queryKey: ['inventory-count-number-search', searchToken],
    queryFn: () => stockApi.searchInventoryCountNumbers(searchToken, 12),
    enabled: isSuggestionsOpen,
    staleTime: 30_000,
  });

  const suggestions = suggestionsResponse?.items ?? [];

  const filteredDifferences = useMemo(() => {
    if (!searchToken) {
      return allDifferences;
    }
    return allDifferences.filter((entry) => entry.count_number.toUpperCase().includes(searchToken));
  }, [allDifferences, searchToken]);

  const totalVisibleItems = useMemo(() => {
    return filteredDifferences.reduce((sum, entry) => sum + entry.items.length, 0);
  }, [filteredDifferences]);

  const searchDifference = () => {
    if (!searchToken) {
      toast.info('Showing all confirmed inventory count differences');
      return;
    }
    if (filteredDifferences.length === 0) {
      toast.error('No confirmed inventory count found for this number');
      return;
    }
    toast.success(`Showing ${filteredDifferences.length} matching inventory count(s)`);
  };

  const renderDifferenceTable = (result: InventoryCountDifferenceResponse) => (
    <div className="hms-card overflow-hidden" key={result.count_number}>
      <div className="grid grid-cols-1 gap-4 border-b border-neutral-200 bg-neutral-50 p-4 md:grid-cols-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Count Number</p>
          <p className="mt-1 text-sm font-semibold text-neutral-900">{result.count_number}</p>
        </div>
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Count Date</p>
          <p className="mt-1 text-sm font-semibold text-neutral-900">{result.count_date}</p>
        </div>
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Count Performed By</p>
          <p className="mt-1 text-sm font-semibold text-neutral-900">{result.count_performed_by}</p>
        </div>
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Total Items</p>
          <p className="mt-1 text-sm font-semibold text-neutral-900">{result.total_items}</p>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-neutral-200 bg-neutral-50">
              <th className="px-4 py-3 text-left font-semibold text-neutral-600">S.No</th>
              <th className="px-4 py-3 text-left font-semibold text-neutral-600">Product Code</th>
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
                <tr key={`${result.count_number}-${item.product_id}-${item.serial_number}-${index}`} className="border-b border-neutral-100">
                  <td className="px-4 py-3">{item.serial_number}</td>
                  <td className="px-4 py-3 text-xs text-neutral-600">{item.product_code || item.product_id}</td>
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
  );

  return (
    <AppLayout title="Inventory Count Difference (Admin)">
      <div className="space-y-6">
        <div className="hms-card p-5">
          <h2 className="font-display text-lg font-semibold text-neutral-900">Find Inventory Count Difference</h2>
          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="relative sm:w-80">
              <label className="hms-label">Inventory Count Number</label>
              <input
                type="text"
                className="hms-input"
                value={countNumber}
                onFocus={() => {
                  setHasTypedSinceFocus(false);
                  setIsSuggestionsOpen(true);
                }}
                onBlur={() => {
                  window.setTimeout(() => setIsSuggestionsOpen(false), 120);
                  setHasTypedSinceFocus(false);
                }}
                onChange={(e) => {
                  setHasTypedSinceFocus(true);
                  setCountNumber(e.target.value.toUpperCase());
                  setIsSuggestionsOpen(true);
                }}
                placeholder="INV-APR-001"
              />
              {isSuggestionsOpen && suggestions.length > 0 && (
                <div className="absolute z-20 mt-1 max-h-52 w-full overflow-auto rounded-lg border border-neutral-200 bg-white shadow-lg">
                  {suggestions.map((item) => (
                    <button
                      key={item}
                      type="button"
                      className="block w-full px-3 py-2 text-left text-sm text-neutral-700 hover:bg-neutral-100"
                      onMouseDown={(event) => {
                        event.preventDefault();
                        setCountNumber(item);
                        setHasTypedSinceFocus(false);
                        setIsSuggestionsOpen(false);
                      }}
                    >
                      {item}
                    </button>
                  ))}
                </div>
              )}
              {isSuggestionsOpen && hasTypedSinceFocus && searchToken && suggestions.length === 0 && (
                <div className="absolute z-20 mt-1 w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-500 shadow-lg">
                  No matching inventory count numbers
                </div>
              )}
            </div>
            <button type="button" className="hms-button-primary" onClick={searchDifference}>
              Apply Filter
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="hms-card p-4">
            <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Confirmed Counts Shown</p>
            <p className="mt-2 text-base font-semibold text-neutral-900">{filteredDifferences.length}</p>
          </div>
          <div className="hms-card p-4">
            <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Total Difference Rows</p>
            <p className="mt-2 text-base font-semibold text-neutral-900">{totalVisibleItems}</p>
          </div>
        </div>

        {isAllDifferencesLoading ? (
          <div className="hms-card p-6 text-sm text-neutral-600">Loading confirmed inventory count differences...</div>
        ) : isAllDifferencesError ? (
          <div className="hms-card p-6 text-sm text-red-600">Failed to load confirmed inventory count differences.</div>
        ) : filteredDifferences.length === 0 ? (
          <div className="hms-card p-6 text-sm text-neutral-600">No confirmed inventory count differences available.</div>
        ) : (
          <div className="space-y-6">
            {filteredDifferences.map((entry) => renderDifferenceTable(entry))}
          </div>
        )}
      </div>
    </AppLayout>
  );
};

export default InventoryCountDifferencePage;
