import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { purchaseApi, CreatePOPayload } from '../api/purchase';
import { suppliersApi } from '../api/suppliers';
import { productsApi } from '../api/products';
import { AppLayout } from '../components/AppLayout';
import { PageEmpty, PageError, PageLoading } from '../components/PageState';
import type { AxiosError } from 'axios';

const poSchema = z.object({
  supplier_id: z.string().min(1, 'Supplier required'),
  order_date: z.string().min(1, 'Order date required'),
  expected_delivery_date: z.string().optional(),
  notes: z.string().optional(),
});

type POForm = z.infer<typeof poSchema>;

interface POLineItem {
  product_id: string;
  quantity: number;
  unit_price: number;
  discount_percent: number;
  gst_rate: number;
}

const PurchaseOrderPage = () => {
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState('');
  const [status, setStatus] = useState<string | null>(null);
  const [lineItems, setLineItems] = useState<POLineItem[]>([]);
  const [newItem, setNewItem] = useState<Partial<POLineItem>>({
    discount_percent: 0,
    gst_rate: 18,
  });

  const posQuery = useQuery({ queryKey: ['purchase-orders', status], queryFn: () => purchaseApi.listPOs(status ?? undefined) });
  const suppliersQuery = useQuery({ queryKey: ['suppliers'], queryFn: suppliersApi.list });
  const productsQuery = useQuery({ queryKey: ['products'], queryFn: productsApi.list });

  const form = useForm<POForm>({
    defaultValues: {
      supplier_id: '',
      order_date: new Date().toISOString().split('T')[0],
      expected_delivery_date: '',
      notes: '',
    },
  });

  const createMutation = useMutation({
    mutationFn: (payload: CreatePOPayload) => purchaseApi.createPO(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchase-orders'] });
      form.reset();
      setLineItems([]);
      setNewItem({ discount_percent: 0, gst_rate: 18 });
      setFormError('');
    },
    onError: (error: unknown) => {
      const axiosErr = error as AxiosError<{ detail?: string | Array<{msg: string}> }>;
      const detail = axiosErr.response?.data?.detail;
      if (typeof detail === 'string') {
        setFormError(detail);
      } else if (Array.isArray(detail)) {
        setFormError(detail.map(d => d.msg).join(', '));
      } else {
        setFormError('Failed to create PO');
      }
    },
  });

  const handleAddLineItem = () => {
    if (
      !newItem.product_id ||
      !newItem.quantity ||
      !newItem.unit_price ||
      newItem.gst_rate === undefined
    ) {
      setFormError('All line item fields required');
      return;
    }

    setLineItems([...lineItems, newItem as POLineItem]);
    setNewItem({ discount_percent: 0, gst_rate: 18 });
    setFormError('');
  };

  const handleRemoveLineItem = (index: number) => {
    setLineItems(lineItems.filter((_, i) => i !== index));
  };

  const onSubmit = async (values: POForm) => {
    if (lineItems.length === 0) {
      setFormError('At least one line item required');
      return;
    }

    const parsed = poSchema.safeParse(values);
    if (!parsed.success) {
      setFormError(parsed.error.issues[0]?.message ?? 'Validation failed');
      return;
    }

    createMutation.mutate({
      supplier_id: parsed.data.supplier_id,
      order_date: parsed.data.order_date,
      expected_delivery_date: parsed.data.expected_delivery_date || undefined,
      notes: parsed.data.notes || undefined,
      status: 'draft',
      items: lineItems.map((item) => ({
        product_id: item.product_id,
        quantity: item.quantity,
        unit_price: Math.round(item.unit_price * 100),
        discount_percent: item.discount_percent || 0,
        gst_rate: item.gst_rate,
      })),
    });
  };

  const pos = posQuery.data?.data.items ?? [];
  const suppliers = suppliersQuery.data?.items ?? [];
  const products = productsQuery.data?.items ?? [];

  return (
    <AppLayout title="Purchase Orders">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Form Card */}
        <div className="hms-card lg:col-span-1">
          <div className="p-5 border-b border-neutral-200">
            <h2 className="font-display text-lg font-bold">New Purchase Order</h2>
          </div>

          <form className="p-5 space-y-4" onSubmit={form.handleSubmit(onSubmit)}>
            <div>
              <label htmlFor="supplier_id" className="hms-label">
                Supplier
              </label>
              <select id="supplier_id" className="hms-input" {...form.register('supplier_id')}>
                <option value="">Select supplier</option>
                {suppliers.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.company_name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="order_date" className="hms-label">
                Order Date
              </label>
              <input id="order_date" type="date" className="hms-input" {...form.register('order_date')} />
            </div>

            <div>
              <label htmlFor="expected_delivery_date" className="hms-label">
                Expected Delivery Date
              </label>
              <input id="expected_delivery_date" type="date" className="hms-input" {...form.register('expected_delivery_date')} />
            </div>

            <div>
              <label htmlFor="notes" className="hms-label">
                Notes
              </label>
              <textarea id="notes" className="hms-input" rows={3} {...form.register('notes')} />
            </div>

            {/* Line Items Section */}
            <div className="pt-4 border-t border-neutral-200">
              <h3 className="font-semibold text-sm mb-3">Line Items</h3>

              <div className="space-y-2 mb-4">
                <div>
                  <label className="hms-label">Product</label>
                  <select
                    className="hms-input"
                    value={newItem.product_id || ''}
                    onChange={(e) => setNewItem({ ...newItem, product_id: e.target.value })}
                  >
                    <option value="">Select product</option>
                    {products.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="hms-label">Quantity</label>
                    <input
                      type="number"
                      className="hms-input"
                      value={newItem.quantity || ''}
                      onChange={(e) => setNewItem({ ...newItem, quantity: parseFloat(e.target.value) })}
                    />
                  </div>
                  <div>
                    <label className="hms-label">Unit Price</label>
                    <input
                      type="number"
                      className="hms-input"
                      value={newItem.unit_price || ''}
                      onChange={(e) => setNewItem({ ...newItem, unit_price: parseFloat(e.target.value) })}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="hms-label">Discount %</label>
                    <input
                      type="number"
                      className="hms-input"
                      value={newItem.discount_percent || 0}
                      onChange={(e) => setNewItem({ ...newItem, discount_percent: parseFloat(e.target.value) })}
                    />
                  </div>
                  <div>
                    <label className="hms-label">GST %</label>
                    <select
                      className="hms-input"
                      value={newItem.gst_rate || 18}
                      onChange={(e) => setNewItem({ ...newItem, gst_rate: parseInt(e.target.value) })}
                    >
                      <option value="0">0%</option>
                      <option value="5">5%</option>
                      <option value="12">12%</option>
                      <option value="18">18%</option>
                      <option value="28">28%</option>
                    </select>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={handleAddLineItem}
                  className="w-full bg-secondary text-white px-3 py-2 rounded text-sm font-medium hover:bg-secondary/90"
                >
                  Add Item
                </button>
              </div>

              {lineItems.length > 0 && (
                <div className="bg-neutral-50 rounded p-3 space-y-2 mb-4 max-h-48 overflow-y-auto">
                  {lineItems.map((item, idx) => {
                    const product = products.find((p) => p.id === item.product_id);
                    return (
                      <div key={idx} className="flex justify-between items-start bg-white p-2 rounded border border-neutral-200">
                        <div className="text-sm flex-1">
                          <div className="font-medium">{product?.name}</div>
                          <div className="text-neutral-600 text-xs">
                            {item.quantity} x {item.unit_price} (GST: {item.gst_rate}%)
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => handleRemoveLineItem(idx)}
                          className="text-danger hover:text-danger/80 text-xs ml-2"
                        >
                          ✕
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {formError && <p className="text-sm text-danger">{formError}</p>}
            {createMutation.isError && <p className="text-sm text-danger">Failed to create PO</p>}
            {createMutation.isSuccess && <p className="text-sm text-success">PO created successfully</p>}

            <button
              type="submit"
              disabled={createMutation.isPending}
              className="w-full bg-primary text-white px-5 py-2.5 rounded font-semibold hover:bg-primary/90 disabled:opacity-60"
            >
              {createMutation.isPending ? 'Creating...' : 'Create PO'}
            </button>
          </form>
        </div>

        {/* List Card */}
        <div className="hms-card lg:col-span-2">
          <div className="p-5 border-b border-neutral-200">
            <h2 className="font-display text-lg font-bold mb-4">Purchase Orders</h2>
            <div className="flex gap-2 flex-wrap">
              <button
                onClick={() => setStatus(null)}
                className={`px-3 py-1 text-sm rounded ${status === null ? 'bg-primary text-white' : 'bg-neutral-100 text-neutral-700'}`}
              >
                All
              </button>
              {['draft', 'confirmed', 'partial', 'received'].map((s) => (
                <button
                  key={s}
                  onClick={() => setStatus(s)}
                  className={`px-3 py-1 text-sm rounded ${status === s ? 'bg-primary text-white' : 'bg-neutral-100 text-neutral-700'}`}
                >
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </button>
              ))}
            </div>
          </div>

          <div className="p-5">
            {posQuery.isLoading && <PageLoading message="Loading purchase orders..." />}
            {posQuery.isError && <PageError message="Failed to load purchase orders" />}
            {!posQuery.isLoading && !posQuery.isError && pos.length === 0 && <PageEmpty message="No purchase orders found" />}
            {!posQuery.isLoading && !posQuery.isError && pos.length > 0 && (
              <table className="w-full text-sm">
                <caption className="sr-only">Purchase orders list</caption>
                <thead className="bg-neutral-50">
                  <tr className="border-y border-neutral-200">
                    <th scope="col" className="px-4 py-3 text-left text-xs font-bold uppercase">
                      PO Number
                    </th>
                    <th scope="col" className="px-4 py-3 text-left text-xs font-bold uppercase">
                      Supplier
                    </th>
                    <th scope="col" className="px-4 py-3 text-left text-xs font-bold uppercase">
                      Order Date
                    </th>
                    <th scope="col" className="px-4 py-3 text-left text-xs font-bold uppercase">
                      Total Amount
                    </th>
                    <th scope="col" className="px-4 py-3 text-left text-xs font-bold uppercase">
                      Status
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-neutral-100">
                  {pos.map((po) => (
                    <tr key={po.id} className="hover:bg-neutral-50">
                      <td className="px-4 py-3">{po.po_number}</td>
                      <td className="px-4 py-3">{suppliers.find((s) => s.id === po.supplier_id)?.company_name || 'Unknown'}</td>
                      <td className="px-4 py-3">{new Date(po.order_date).toLocaleDateString('en-IN')}</td>
                      <td className="px-4 py-3">₹{(po.total_amount / 100).toFixed(2)}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-block px-2 py-1 rounded text-xs font-semibold ${po.status === 'draft' ? 'bg-yellow-100 text-yellow-700' : po.status === 'confirmed' ? 'bg-blue-100 text-blue-700' : 'bg-green-100 text-green-700'}`}>
                          {po.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </AppLayout>
  );
};

export default PurchaseOrderPage;
