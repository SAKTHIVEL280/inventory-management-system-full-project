import { useEffect, useMemo, useState, type FocusEvent } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';

import { AppLayout } from '../components/AppLayout';
import { productsApi } from '../api/products';
import { stockApi } from '../api/stock';
import { useAuthStore } from '../store/auth';

interface InventoryCountDraftItem {
  serial_number: number;
  product_id: string;
  product_description: string;
  quantity: number;
  batch_no: string;
  manufacture_date: string;
  expiry_date: string;
}

const todayIso = new Date().toISOString().slice(0, 10);

const clearLeadingZeroOnFocus = (event: FocusEvent<HTMLInputElement>) => {
  const currentValue = event.currentTarget.value;
  if (currentValue === '0') {
    event.currentTarget.value = '';
  }
};

const InventoryCountPage = () => {
  const user = useAuthStore((state) => state.user);
  const [countDate, setCountDate] = useState(todayIso);
  const [countNumber, setCountNumber] = useState('');
  const [countPerformedBy, setCountPerformedBy] = useState(user?.full_name || '');
  const [items, setItems] = useState<InventoryCountDraftItem[]>([]);
  const [isQuantityFocused, setIsQuantityFocused] = useState(false);

  const [entry, setEntry] = useState<InventoryCountDraftItem>({
    serial_number: 1,
    product_id: '',
    product_description: '',
    quantity: 0,
    batch_no: '',
    manufacture_date: '',
    expiry_date: '',
  });

  const { data: productsResponse } = useQuery({
    queryKey: ['products-all-for-inventory-count'],
    queryFn: productsApi.listAll,
  });

  const products = useMemo(() => productsResponse?.items ?? [], [productsResponse?.items]);

  const previewMutation = useMutation({
    mutationFn: (dateValue: string) => stockApi.getInventoryCountNumberPreview(dateValue),
    onSuccess: (data) => setCountNumber(data.count_number),
    onError: () => setCountNumber(''),
  });

  useEffect(() => {
    previewMutation.mutate(countDate);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [countDate]);

  useEffect(() => {
    if (user?.full_name) {
      setCountPerformedBy((prev) => prev || user.full_name);
    }
  }, [user?.full_name]);

  const createMutation = useMutation({
    mutationFn: stockApi.createInventoryCount,
    onSuccess: (data) => {
      toast.success(`Inventory count ${data.count_number} confirmed.`);
      setItems([]);
      setEntry({
        serial_number: 1,
        product_id: '',
        product_description: '',
        quantity: 0,
        batch_no: '',
        manufacture_date: '',
        expiry_date: '',
      });
      previewMutation.mutate(countDate);
    },
    onError: (error: unknown) => {
      const message = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(message || 'Failed to confirm inventory count');
    },
  });

  const selectedProduct = useMemo(
    () => products.find((p) => p.id === entry.product_id),
    [products, entry.product_id]
  );

  const addItem = () => {
    if (!entry.serial_number || !entry.product_id || entry.quantity < 0) {
      toast.error('Please enter Serial Number, Product Code and valid Quantity.');
      return;
    }

    const itemToAdd: InventoryCountDraftItem = {
      ...entry,
      product_description: entry.product_description || selectedProduct?.description || selectedProduct?.name || '',
    };

    setItems((prev) => [...prev, itemToAdd]);
    setEntry({
      serial_number: entry.serial_number + 1,
      product_id: '',
      product_description: '',
      quantity: 0,
      batch_no: '',
      manufacture_date: '',
      expiry_date: '',
    });
  };

  const removeItem = (index: number) => {
    setItems((prev) => prev.filter((_, i) => i !== index));
  };

  const canConfirm = Boolean(
    countNumber &&
      countDate &&
      countPerformedBy.trim() &&
      items.length > 0 &&
      !createMutation.isPending
  );

  const confirmInventoryCount = () => {
    if (!canConfirm) return;

    createMutation.mutate({
      count_date: countDate,
      count_performed_by: countPerformedBy.trim(),
      items: items.map((item) => ({
        serial_number: item.serial_number,
        product_id: item.product_id,
        product_description: item.product_description || null,
        quantity: Number(item.quantity || 0),
        batch_no: item.batch_no || null,
        manufacture_date: item.manufacture_date || null,
        expiry_date: item.expiry_date || null,
      })),
    });
  };

  return (
    <AppLayout title="Inventory Count">
      <div className="space-y-6">
        <div className="hms-card p-5">
          <h2 className="font-display text-lg font-semibold text-neutral-900">Inventory Count Header</h2>
          <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
            <div>
              <label className="hms-label">Inventory Count Number</label>
              <input
                type="text"
                className="hms-input bg-neutral-50"
                value={countNumber}
                readOnly
                placeholder="Auto-generated"
              />
            </div>
            <div>
              <label className="hms-label">Count Date</label>
              <input
                type="date"
                className="hms-input"
                value={countDate}
                onChange={(e) => setCountDate(e.target.value)}
              />
            </div>
            <div>
              <label className="hms-label">Count Performed By</label>
              <input
                type="text"
                className="hms-input"
                value={countPerformedBy}
                onChange={(e) => setCountPerformedBy(e.target.value)}
                placeholder="Enter performer name"
              />
            </div>
          </div>
        </div>

        <div className="hms-card p-5">
          <h2 className="font-display text-lg font-semibold text-neutral-900">Add Inventory Count Line</h2>
          <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-4 xl:grid-cols-8">
            <div>
              <label className="hms-label">Serial Number</label>
              <input
                type="number"
                className="hms-input"
                min={1}
                value={entry.serial_number}
                onChange={(e) => setEntry((prev) => ({ ...prev, serial_number: Number(e.target.value || 0) }))}
              />
            </div>
            <div className="xl:col-span-2">
              <label className="hms-label">Product Code</label>
              <select
                className="hms-input"
                value={entry.product_id}
                onChange={(e) => {
                  const product = products.find((p) => p.id === e.target.value);
                  setEntry((prev) => ({
                    ...prev,
                    product_id: e.target.value,
                    product_description: product?.description || product?.name || prev.product_description,
                  }));
                }}
              >
                <option value="">Select Product</option>
                {products.map((product) => (
                  <option key={product.id} value={product.id}>
                    {product.product_code || product.id} - {product.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="xl:col-span-2">
              <label className="hms-label">Product Description</label>
              <input
                type="text"
                className="hms-input"
                value={entry.product_description}
                onChange={(e) => setEntry((prev) => ({ ...prev, product_description: e.target.value }))}
                placeholder="Description"
              />
            </div>
            <div>
              <label className="hms-label">Quantity</label>
              <input
                type="number"
                className="hms-input"
                min={0}
                step="0.0001"
                value={isQuantityFocused && entry.quantity === 0 ? '' : entry.quantity}
                onFocus={(event) => {
                  setIsQuantityFocused(true);
                  clearLeadingZeroOnFocus(event);
                }}
                onBlur={() => setIsQuantityFocused(false)}
                onChange={(e) => setEntry((prev) => ({ ...prev, quantity: Number(e.target.value || 0) }))}
              />
            </div>
            <div>
              <label className="hms-label">Batch Number</label>
              <input
                type="text"
                className="hms-input"
                value={entry.batch_no}
                onChange={(e) => setEntry((prev) => ({ ...prev, batch_no: e.target.value }))}
                placeholder="Batch"
              />
            </div>
            <div>
              <label className="hms-label">Mfg Date</label>
              <input
                type="date"
                className="hms-input"
                value={entry.manufacture_date}
                onChange={(e) => setEntry((prev) => ({ ...prev, manufacture_date: e.target.value }))}
              />
            </div>
            <div>
              <label className="hms-label">Exp Date</label>
              <input
                type="date"
                className="hms-input"
                value={entry.expiry_date}
                onChange={(e) => setEntry((prev) => ({ ...prev, expiry_date: e.target.value }))}
              />
            </div>
          </div>

          <div className="mt-4 flex justify-end">
            <button type="button" className="hms-button-primary" onClick={addItem}>
              Add Entry
            </button>
          </div>
        </div>

        <div className="hms-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-neutral-200 bg-neutral-50">
                  <th className="px-4 py-3 text-left font-semibold text-neutral-600">Serial Number</th>
                  <th className="px-4 py-3 text-left font-semibold text-neutral-600">Product Code</th>
                  <th className="px-4 py-3 text-left font-semibold text-neutral-600">Product Description</th>
                  <th className="px-4 py-3 text-right font-semibold text-neutral-600">Quantity</th>
                  <th className="px-4 py-3 text-left font-semibold text-neutral-600">Batch Number</th>
                  <th className="px-4 py-3 text-left font-semibold text-neutral-600">Mfg Date</th>
                  <th className="px-4 py-3 text-left font-semibold text-neutral-600">Exp Date</th>
                  <th className="px-4 py-3 text-center font-semibold text-neutral-600">Action</th>
                </tr>
              </thead>
              <tbody>
                {items.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-8 text-center text-neutral-500">No entries added yet</td>
                  </tr>
                ) : (
                  items.map((item, index) => (
                    <tr key={`${item.serial_number}-${item.product_id}-${index}`} className="border-b border-neutral-100">
                      <td className="px-4 py-3">{item.serial_number}</td>
                      <td className="px-4 py-3 text-xs text-neutral-600">{products.find((p) => p.id === item.product_id)?.product_code || item.product_id}</td>
                      <td className="px-4 py-3">{item.product_description || '—'}</td>
                      <td className="px-4 py-3 text-right">{item.quantity}</td>
                      <td className="px-4 py-3">{item.batch_no || '—'}</td>
                      <td className="px-4 py-3">{item.manufacture_date || '—'}</td>
                      <td className="px-4 py-3">{item.expiry_date || '—'}</td>
                      <td className="px-4 py-3 text-center">
                        <button
                          type="button"
                          className="hms-button-danger-outline"
                          onClick={() => removeItem(index)}
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="flex justify-end">
          <button
            type="button"
            className="hms-button-primary disabled:cursor-not-allowed disabled:border-neutral-300 disabled:bg-neutral-300 disabled:text-neutral-600 disabled:shadow-none disabled:opacity-100"
            disabled={!canConfirm}
            onClick={confirmInventoryCount}
          >
            {createMutation.isPending ? 'Confirming...' : 'Confirm'}
          </button>
        </div>
      </div>
    </AppLayout>
  );
};

export default InventoryCountPage;
