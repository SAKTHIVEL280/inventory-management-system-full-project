import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { purchaseApi, CreatePOPayload, PurchaseOrder, PurchaseLineItem } from '../api/purchase';
import { suppliersApi } from '../api/suppliers';
import { productsApi } from '../api/products';
import { AppLayout } from '../components/AppLayout';
import { PageEmpty, PageError, PageLoading } from '../components/PageState';
import type { AxiosError } from 'axios';
import { toast } from 'sonner';
import { confirmToast } from '../utils/toast';
import { todayLocalDateInputValue } from '../utils/date';
import { emptyWhenZero } from '../utils/numberInput';

const poSchema = z.object({
  supplier_id: z.string().min(1, 'Supplier required'),
  order_date: z.string().min(1, 'Order date required'),
  expected_delivery_date: z.string().optional(),
  currency_code: z.string().default('INR'),
  exchange_rate: z.coerce.number().min(0.000001).default(1.0),
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

// Helper to calculate line total
const calculateLineTotal = (item: POLineItem): number => {
  const gross = item.quantity * item.unit_price;
  const discount = gross * (item.discount_percent || 0) / 100;
  const taxable = gross - discount;
  const gst = taxable * (item.gst_rate || 0) / 100;
  return taxable + gst;
};

// Helper to calculate totals
const calculateTotals = (items: POLineItem[]) => {
  return items.reduce(
    (acc, item) => {
      const gross = item.quantity * item.unit_price;
      const discount = gross * (item.discount_percent || 0) / 100;
      const taxable = gross - discount;
      const gst = taxable * (item.gst_rate || 0) / 100;
      
      acc.subtotal += gross;
      acc.discount += discount;
      acc.taxable += taxable;
      acc.gst += gst;
      acc.total += taxable + gst;
      return acc;
    },
    { subtotal: 0, discount: 0, taxable: 0, gst: 0, total: 0 }
  );
};

const PurchaseOrderPage = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState('');
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [archiveView, setArchiveView] = useState<'active' | 'archived'>('active');
  const [searchQuery, setSearchQuery] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [lineItems, setLineItems] = useState<POLineItem[]>([]);
  const [newItem, setNewItem] = useState<Partial<POLineItem>>({
    discount_percent: 0,
    gst_rate: 18,
  });
  const [selectedPO, setSelectedPO] = useState<PurchaseOrder | null>(null);
  const [showPODetail, setShowPODetail] = useState(false);
  const [submitMode, setSubmitMode] = useState<'draft' | 'sent'>('draft');
  const [poDetailItems, setPODetailItems] = useState<PurchaseLineItem[]>([]);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const posQuery = useQuery({
    queryKey: ['purchase-orders', statusFilter, archiveView],
    queryFn: () => purchaseApi.listPOs(statusFilter ?? undefined, 1, 20, { archived_only: archiveView === 'archived' }),
  });
  const suppliersQuery = useQuery({ queryKey: ['suppliers'], queryFn: () => suppliersApi.list() });
  const productsQuery = useQuery({ queryKey: ['products'], queryFn: productsApi.listAll });

  const form = useForm<POForm>({
    defaultValues: {
      supplier_id: '',
      order_date: todayLocalDateInputValue(),
      expected_delivery_date: '',
      currency_code: 'INR',
      exchange_rate: 1.0,
      notes: '',
    },
  });

  const createMutation = useMutation({
    mutationFn: (payload: CreatePOPayload) => purchaseApi.createPO(payload),
    onSuccess: async (response) => {
      if (submitMode === 'sent') {
        try {
          await purchaseApi.updatePOStatus(response.data.id, 'sent');
          toast.success('Purchase Order created and sent');
        } catch {
          toast.warning('PO created, but failed to mark as sent');
        }
      }

      queryClient.invalidateQueries({ queryKey: ['purchase-orders'] });
      form.reset();
      setLineItems([]);
      setNewItem({ discount_percent: 0, gst_rate: 18 });
      setFormError('');
      setIsFormOpen(false);
      if (submitMode === 'draft') {
        toast.success('Purchase Order saved as draft');
      }
      setSubmitMode('draft');
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

  const sendMutation = useMutation({
    mutationFn: (id: string) => purchaseApi.updatePOStatus(id, 'sent'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchase-orders'] });
      toast.success('Purchase Order sent');
      setShowPODetail(false);
    },
    onError: (error: unknown) => {
      const axiosErr = error as AxiosError<{ detail?: string }>;
      const detail = axiosErr.response?.data?.detail;
      toast.error(detail || 'Failed to send PO');
    },
  });

  const cancelPOMutation = useMutation({
    mutationFn: (id: string) => purchaseApi.updatePOStatus(id, 'cancelled'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchase-orders'] });
      toast.success('Purchase Order cancelled');
      setShowPODetail(false);
    },
    onError: (error: unknown) => {
      const axiosErr = error as AxiosError<{ detail?: string }>;
      const detail = axiosErr.response?.data?.detail;
      toast.error(detail || 'Failed to cancel PO');
    },
  });

  const downloadPOPdf = async (poId: string, poNumber: string) => {
    try {
      toast.info('Generating PDF...');
      const response = await purchaseApi.downloadPOPdf(poId);
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `PO-${poNumber}.pdf`);
      document.body.appendChild(link);
      link.click();
      window.URL.revokeObjectURL(url);
      link.remove();
      toast.success('PDF downloaded successfully');
    } catch (error: unknown) {
      const axiosErr = error as AxiosError<{ detail?: string }>;
      const detail = axiosErr.response?.data?.detail;

      if (axiosErr.code === 'ERR_NETWORK') {
        toast.error('Failed to download PDF: network/CORS issue. Use the same host for frontend and backend (localhost vs 127.0.0.1).');
      } else if (typeof detail === 'string' && detail.trim()) {
        toast.error(`Failed to download PDF: ${detail}`);
      } else {
        toast.error('Failed to download PDF');
      }
      console.error(error);
    }
  };

  const handleDownloadPDF = async () => {
    if (!selectedPO) return;
    await downloadPOPdf(selectedPO.id, selectedPO.po_number);
  };

  const handleOpenPO = async (po: PurchaseOrder) => {
    setSelectedPO(po);
    setShowPODetail(true);
    setPODetailItems([]);
    setLoadingDetail(true);
    try {
      const res = await purchaseApi.getPO(po.id);
      setPODetailItems(res.data.items || []);
      // Update selectedPO with the latest data from server
      setSelectedPO(res.data.purchase_order);
    } catch {
      setPODetailItems([]);
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleSendPO = () => {
    if (selectedPO) {
      confirmToast('Are you sure you want to send this PO? Once sent, it cannot be modified.', {
        onConfirm: () => sendMutation.mutate(selectedPO.id),
        type: 'confirm',
      });
    }
  };

  const handleCancelPO = () => {
    if (selectedPO) {
      confirmToast('Are you sure you want to cancel this PO? This action cannot be undone.', {
        onConfirm: () => cancelPOMutation.mutate(selectedPO.id),
        type: 'danger',
      });
    }
  };

  const handleArchiveToggle = async (poId: string, archived: boolean) => {
    try {
      if (archived) {
        await purchaseApi.restorePO(poId);
      } else {
        await purchaseApi.archivePO(poId);
      }
      queryClient.invalidateQueries({ queryKey: ['purchase-orders'] });
      if (selectedPO?.id === poId) {
        setShowPODetail(false);
        setSelectedPO(null);
      }
    } catch {
      toast.error(archived ? 'Failed to restore PO' : 'Failed to archive PO');
    }
  };

  const handleAddLineItem = () => {
    if (
      !newItem.product_id ||
      !newItem.quantity ||
      !newItem.unit_price ||
      newItem.gst_rate === undefined
    ) {
      toast.error('All line item fields are required. Please fill in Product, Quantity, Unit Price, and GST rate.');
      return;
    }

    // Check for duplicate product
    const existingIndex = lineItems.findIndex(item => item.product_id === newItem.product_id);
    if (existingIndex !== -1) {
      const productName = products.find(p => p.id === newItem.product_id)?.name;
      toast.error(`Product "${productName}" is already added. Remove it first or update the quantity.`);
      return;
    }

    setLineItems([...lineItems, newItem as POLineItem]);
    setNewItem({ discount_percent: 0, gst_rate: 18 });
    toast.success('Item added to purchase order');
  };

  const handleRemoveLineItem = (index: number) => {
    const item = lineItems[index];
    const productName = products.find(p => p.id === item.product_id)?.name || 'This item';
    
    confirmToast(`Remove ${productName} from this purchase order?`, {
      onConfirm: () => {
        setLineItems(lineItems.filter((_, i) => i !== index));
        toast.success('Item removed successfully');
      },
      type: 'warning',
    });
  };

  // Auto-fill price and GST when product is selected
  const handleProductSelect = (productId: string) => {
    const product = products.find(p => p.id === productId);
    if (product) {
      setNewItem({
        ...newItem,
        product_id: productId,
        unit_price: product.purchase_price / 100, // Convert from paise to rupees
        gst_rate: product.gst_rate,
      });
    } else {
      setNewItem({ ...newItem, product_id: productId });
    }
  };

  const onSubmit = async (values: POForm) => {
    // Auto-add any pending line item that hasn't been explicitly added yet
    let finalLineItems = [...lineItems];
    if (
      newItem.product_id &&
      newItem.quantity &&
      newItem.unit_price &&
      newItem.gst_rate !== undefined
    ) {
      finalLineItems = [...finalLineItems, newItem as POLineItem];
      setLineItems(finalLineItems);
      setNewItem({ discount_percent: 0, gst_rate: 18 });
    }

    if (finalLineItems.length === 0) {
      toast.error('At least one line item is required. Please add a product with quantity and price.');
      return;
    }

    const parsed = poSchema.safeParse(values);
    if (!parsed.success) {
      const errorMsg = parsed.error.issues[0]?.message ?? 'Validation failed';
      toast.error(errorMsg);
      return;
    }

    createMutation.mutate({
      supplier_id: parsed.data.supplier_id,
      order_date: parsed.data.order_date,
      expected_delivery_date: parsed.data.expected_delivery_date || undefined,
      currency_code: parsed.data.currency_code,
      exchange_rate: parsed.data.exchange_rate,
      notes: parsed.data.notes || undefined,
      status: submitMode,
      items: finalLineItems.map((item) => ({
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

  const supplierNameById = (supplierId: string) => {
    const supplier = suppliers.find((s) => s.id === supplierId);
    return supplier ? supplier.company_name : `Invalid supplier (${supplierId.slice(0, 8)}...)`;
  };

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

  const filteredPOs = pos.filter((po) => {
    const term = searchQuery.trim().toLowerCase();
    const supplierName = supplierNameById(po.supplier_id).toLowerCase();
    const matchesSearch =
      !term ||
      po.po_number.toLowerCase().includes(term) ||
      supplierName.includes(term) ||
      po.status.toLowerCase().includes(term) ||
      po.order_date.toLowerCase().includes(term);
    const matchesFrom = !dateFrom || po.order_date >= dateFrom;
    const matchesTo = !dateTo || po.order_date <= dateTo;
    return matchesSearch && matchesFrom && matchesTo;
  });

  return (
    <AppLayout title="Purchase Orders">
      <div className="space-y-6">
        {/* Form Card */}
        <div className="hms-card overflow-hidden">
          <div className="border-b border-neutral-200 p-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="font-display text-lg font-bold">New Purchase Order</h2>
                <p className="text-xs text-neutral-500">Create a PO in a collapsible form and keep the list full width.</p>
              </div>
              <div className="flex items-center gap-2">
                {!isFormOpen && (
                  <button
                    type="button"
                    onClick={() => setIsFormOpen(true)}
                    className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white transition hover:bg-primary/90"
                  >
                    + New PO
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setIsFormOpen((prev) => !prev)}
                  className="inline-flex items-center gap-1 rounded-lg border border-neutral-200 px-3 py-2 text-sm font-semibold text-neutral-700 transition hover:bg-neutral-50"
                >
                  <span className="material-icons text-base" aria-hidden="true">{isFormOpen ? 'expand_less' : 'expand_more'}</span>
                  {isFormOpen ? 'Hide Form' : 'Show Form'}
                </button>
              </div>
            </div>
          </div>

          {isFormOpen && (
            <form className="grid grid-cols-1 gap-4 p-5 md:grid-cols-2 xl:grid-cols-4" onSubmit={form.handleSubmit(onSubmit)}>
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

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="currency_code" className="hms-label">Currency</label>
                <select id="currency_code" className="hms-input" {...form.register('currency_code')}>
                  <option value="INR">INR (₹)</option>
                  <option value="USD">USD ($)</option>
                  <option value="EUR">EUR (€)</option>
                  <option value="GBP">GBP (£)</option>
                </select>
              </div>
              <div>
                <label htmlFor="exchange_rate" className="hms-label">Exchange Rate</label>
                <input id="exchange_rate" type="number" step="0.0001" className="hms-input" {...form.register('exchange_rate')} disabled={form.watch('currency_code') === 'INR'} />
              </div>
            </div>

            <div>
              <label htmlFor="notes" className="hms-label">
                Notes
              </label>
              <textarea id="notes" className="hms-input" rows={3} {...form.register('notes')} />
            </div>

            {/* Line Items Section */}
            <div className="border-t border-neutral-200 pt-4 md:col-span-2 xl:col-span-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-sm">Line Items</h3>
                <span className="text-xs text-neutral-500">{lineItems.length} item(s) added</span>
              </div>

              <div className="space-y-2 mb-4">
                <div>
                  <label className="hms-label">Product *</label>
                  <select
                    className="hms-input"
                    value={newItem.product_id || ''}
                    onChange={(e) => handleProductSelect(e.target.value)}
                  >
                    <option value="">Select product</option>
                    {products
                      .slice()
                      .sort((a, b) => a.name.localeCompare(b.name))
                      .map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name} (₹{(p.purchase_price / 100).toFixed(2)} | GST: {p.gst_rate}%)
                        </option>
                      ))}
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="hms-label">Quantity *</label>
                    <input
                      type="number"
                      className="hms-input"
                      value={newItem.quantity || ''}
                      onChange={(e) => setNewItem({ ...newItem, quantity: parseFloat(e.target.value) || 0 })}
                      min="0.01"
                      step="0.01"
                    />
                  </div>
                  <div>
                    <label className="hms-label">Unit Price (₹) *</label>
                    <input
                      type="number"
                      className="hms-input"
                      value={newItem.unit_price || ''}
                      onChange={(e) => setNewItem({ ...newItem, unit_price: parseFloat(e.target.value) || 0 })}
                      min="0"
                      step="0.01"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="hms-label">Discount %</label>
                    <input
                      type="number"
                      className="hms-input"
                      value={emptyWhenZero(newItem.discount_percent)}
                      onChange={(e) => setNewItem({ ...newItem, discount_percent: parseFloat(e.target.value) || 0 })}
                      min="0"
                      max="100"
                      step="0.01"
                    />
                  </div>
                  <div>
                    <label className="hms-label">GST % *</label>
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

                {/* ADD ITEM BUTTON - This should be visible */}
                <button
                  type="button"
                  onClick={handleAddLineItem}
                  className="w-full bg-secondary text-white px-3 py-2.5 rounded text-sm font-semibold hover:bg-secondary/90 transition flex items-center justify-center gap-2 mt-2"
                  style={{ backgroundColor: '#059669' }}
                >
                  <span className="material-icons text-sm">add_circle</span>
                  Add Item to PO
                </button>
              </div>

              {lineItems.length > 0 && (
                <div className="bg-neutral-50 rounded-lg p-4 mb-4">
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {lineItems.map((item, idx) => {
                      const product = products.find((p) => p.id === item.product_id);
                      const lineTotal = calculateLineTotal(item);
                      return (
                        <div key={idx} className="flex justify-between items-start bg-white p-3 rounded border border-neutral-200">
                          <div className="flex-1">
                            <div className="font-medium text-neutral-900">{product?.name || 'Unknown Product'}</div>
                            <div className="text-neutral-600 text-xs mt-1 space-x-2">
                              <span>Qty: {item.quantity}</span>
                              <span>•</span>
                              <span>₹{item.unit_price.toFixed(2)}/unit</span>
                              <span>•</span>
                              <span>Disc: {item.discount_percent}%</span>
                              <span>•</span>
                              <span>GST: {item.gst_rate}%</span>
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="font-semibold text-neutral-900">₹{lineTotal.toFixed(2)}</div>
                            <button
                              type="button"
                              onClick={() => handleRemoveLineItem(idx)}
                              className="text-danger hover:text-danger/80 text-xs mt-1 font-medium"
                            >
                              Remove
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {/* Totals Summary */}
                  <div className="mt-4 pt-4 border-t border-neutral-200 space-y-1">
                    {(() => {
                      const totals = calculateTotals(lineItems);
                      return (
                        <>
                          <div className="flex justify-between text-xs">
                            <span className="text-neutral-600">Subtotal:</span>
                            <span className="font-medium">₹{totals.subtotal.toFixed(2)}</span>
                          </div>
                          <div className="flex justify-between text-xs">
                            <span className="text-neutral-600">Discount:</span>
                            <span className="font-medium text-red-600">-₹{totals.discount.toFixed(2)}</span>
                          </div>
                          <div className="flex justify-between text-xs">
                            <span className="text-neutral-600">Taxable Amount:</span>
                            <span className="font-medium">₹{totals.taxable.toFixed(2)}</span>
                          </div>
                          <div className="flex justify-between text-xs">
                            <span className="text-neutral-600">GST:</span>
                            <span className="font-medium">₹{totals.gst.toFixed(2)}</span>
                          </div>
                          <div className="flex justify-between text-sm font-bold pt-2 border-t border-neutral-200 mt-2">
                            <span className="text-neutral-900">Grand Total:</span>
                            <span className="text-primary">₹{totals.total.toFixed(2)}</span>
                          </div>
                        </>
                      );
                    })()}
                  </div>
                </div>
              )}
            </div>

            <div className="md:col-span-2 xl:col-span-4">
              {formError && <p className="text-sm text-danger">{formError}</p>}
              {createMutation.isError && <p className="text-sm text-danger">Failed to create PO</p>}
              {createMutation.isSuccess && <p className="text-sm text-success">PO created successfully</p>}
            </div>

            <div className="flex flex-col gap-3 md:col-span-2 xl:col-span-4 sm:flex-row">
              <button
                type="submit"
                onClick={() => setSubmitMode('draft')}
                disabled={createMutation.isPending}
                className="bg-primary text-white px-5 py-2.5 rounded font-semibold hover:bg-primary/90 disabled:opacity-60"
              >
                {createMutation.isPending ? 'Saving...' : 'Save as Draft'}
              </button>
              <button
                type="submit"
                onClick={() => setSubmitMode('sent')}
                disabled={createMutation.isPending}
                className="bg-secondary text-white px-5 py-2.5 rounded font-semibold hover:bg-secondary/90 disabled:opacity-60"
              >
                {createMutation.isPending ? 'Saving...' : 'Save and Send'}
              </button>
            </div>
          </form>
          )}
        </div>

        {/* List Card */}
        <div className="hms-card overflow-hidden">
          <div className="p-5 border-b border-neutral-200">
            <h2 className="font-display text-lg font-bold mb-4">Purchase Orders</h2>
            <div className="flex gap-2 flex-wrap">
              <button
                onClick={() => setStatusFilter(null)}
                className={`px-3 py-1 text-sm rounded ${statusFilter === null ? 'bg-primary text-white' : 'bg-neutral-100 text-neutral-700'}`}
              >
                All
              </button>
              {['draft', 'sent', 'partial', 'received', 'cancelled'].map((s) => (
                <button
                  key={s}
                  onClick={() => setStatusFilter(s)}
                  className={`px-3 py-1 text-sm rounded ${statusFilter === s ? 'bg-primary text-white' : 'bg-neutral-100 text-neutral-700'}`}
                >
                  {s === 'sent' ? 'Sent / Approved' : s.charAt(0).toUpperCase() + s.slice(1)}
                </button>
              ))}
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <select
                className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm"
                value={archiveView}
                onChange={(e) => setArchiveView(e.target.value as 'active' | 'archived')}
              >
                <option value="active">Active Only</option>
                <option value="archived">Archived Only</option>
              </select>
              <input
                type="text"
                className="w-64 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm"
                placeholder="Search PO #, supplier, status..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              <div className="inline-flex items-center gap-2 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm">
                <span className="text-xs font-semibold uppercase tracking-wide text-neutral-500">From</span>
                <input
                  type="date"
                  className="bg-transparent text-sm outline-none"
                  value={dateFrom}
                  max={dateTo || undefined}
                  onChange={(e) => handleDateFromChange(e.target.value)}
                  title="Order date from"
                />
              </div>
              <div className="inline-flex items-center gap-2 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm">
                <span className="text-xs font-semibold uppercase tracking-wide text-neutral-500">To</span>
                <input
                  type="date"
                  className="bg-transparent text-sm outline-none"
                  value={dateTo}
                  min={dateFrom || undefined}
                  onChange={(e) => handleDateToChange(e.target.value)}
                  title="Order date to"
                />
              </div>
            </div>
          </div>

          <div className="p-5">
            {posQuery.isLoading && <PageLoading message="Loading purchase orders..." />}
            {posQuery.isError && <PageError message="Failed to load purchase orders" />}
            {!posQuery.isLoading && !posQuery.isError && filteredPOs.length === 0 && <PageEmpty message="No purchase orders found" />}
            {!posQuery.isLoading && !posQuery.isError && filteredPOs.length > 0 && (
              <div className="overflow-x-auto">
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
                      <th scope="col" className="px-4 py-3 text-left text-xs font-bold uppercase">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-100">
                    {filteredPOs.map((po) => (
                      <tr key={po.id} className="cursor-pointer hover:bg-neutral-50" onClick={() => handleOpenPO(po)}>
                        <td className="px-4 py-3 font-medium">{po.po_number}</td>
                        <td className="px-4 py-3">{supplierNameById(po.supplier_id)}</td>
                        <td className="px-4 py-3">{new Date(po.order_date).toLocaleDateString('en-IN')}</td>
                        <td className="px-4 py-3">₹{(po.total_amount / 100).toFixed(2)}</td>
                        <td className="px-4 py-3">
                          <span className={`inline-block px-2 py-1 rounded text-xs font-semibold ${
                            po.status === 'draft' ? 'bg-yellow-100 text-yellow-700' :
                            po.status === 'sent' ? 'bg-blue-100 text-blue-700' :
                            po.status === 'partial' ? 'bg-orange-100 text-orange-700' :
                            po.status === 'received' ? 'bg-green-100 text-green-700' :
                            'bg-gray-100 text-gray-700'
                          }`}>
                            {po.status === 'sent' ? 'Sent / Approved' : po.status}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <button
                              onClick={(e) => { e.stopPropagation(); handleOpenPO(po); }}
                              className="rounded border border-primary/20 bg-primary/5 px-2.5 py-1 text-xs font-semibold text-primary hover:bg-primary/10"
                            >
                              View
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                void downloadPOPdf(po.id, po.po_number);
                              }}
                              className="inline-flex items-center gap-1 rounded border border-neutral-200 bg-white px-2.5 py-1 text-xs font-semibold text-neutral-700 hover:bg-neutral-50"
                              title="Download PDF"
                            >
                              <span className="material-icons text-sm" aria-hidden="true">picture_as_pdf</span>
                              Download PDF
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                void handleArchiveToggle(po.id, archiveView === 'archived');
                              }}
                              className={`rounded border px-2.5 py-1 text-xs font-semibold ${archiveView === 'archived' ? 'border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100' : 'border-red-200 bg-red-50 text-red-700 hover:bg-red-100'}`}
                            >
                              {archiveView === 'archived' ? 'Restore' : 'Archive'}
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {!posQuery.isLoading && !posQuery.isError && (
              <p className="border-t border-neutral-200 px-1 pt-3 text-xs text-neutral-500">Showing {filteredPOs.length} of {pos.length}</p>
            )}
          </div>
        </div>

        {/* PO Detail Modal */}
        {showPODetail && selectedPO && (
          <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4 backdrop-blur-sm" onClick={() => setShowPODetail(false)}>
            <div className="hms-card my-8 w-full max-w-4xl space-y-6 p-6" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="font-display text-xl font-bold">Purchase Order: {selectedPO.po_number}</h2>
                  <p className="text-sm text-neutral-600 mt-1">Supplier: {supplierNameById(selectedPO.supplier_id)}</p>
                </div>
                <div className="flex items-center gap-3">
                  <button onClick={handleDownloadPDF} className="flex h-9 w-9 items-center justify-center rounded-lg border border-neutral-200 text-neutral-600 transition hover:bg-neutral-50 hover:text-primary" title="Download PDF">
                    <span className="material-icons text-[20px]">picture_as_pdf</span>
                  </button>
                  <button onClick={() => setShowPODetail(false)} className="text-neutral-400 hover:text-neutral-600 text-2xl">&times;</button>
                </div>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 bg-neutral-50 p-4 rounded-lg">
                <div>
                  <p className="text-xs text-neutral-600">Order Date</p>
                  <p className="font-medium">{new Date(selectedPO.order_date).toLocaleDateString('en-IN')}</p>
                </div>
                <div>
                  <p className="text-xs text-neutral-600">Status</p>
                  <span className={`inline-block px-2 py-1 rounded text-xs font-semibold ${
                    selectedPO.status === 'draft' ? 'bg-yellow-100 text-yellow-700' :
                    selectedPO.status === 'sent' ? 'bg-blue-100 text-blue-700' :
                    selectedPO.status === 'partial' ? 'bg-orange-100 text-orange-700' :
                    selectedPO.status === 'received' ? 'bg-green-100 text-green-700' :
                    'bg-gray-100 text-gray-700'
                  }`}>
                    {selectedPO.status === 'sent' ? 'Sent / Approved' : selectedPO.status}
                  </span>
                </div>
                <div>
                  <p className="text-xs text-neutral-600">Total Amount</p>
                  <p className="font-medium">
                    {selectedPO.currency_code === 'INR' ? '₹' : selectedPO.currency_code}{' '}
                    {(selectedPO.total_amount / 100).toFixed(2)}
                  </p>
                </div>
              </div>

              {/* Line Items */}
              <div>
                <h3 className="text-sm font-semibold mb-2">Line Items</h3>
                {loadingDetail ? (
                  <p className="text-sm text-neutral-500 py-4 text-center">Loading items...</p>
                ) : poDetailItems.length === 0 ? (
                  <p className="text-sm text-neutral-400 py-4 text-center">No items found</p>
                ) : (
                  <div className="overflow-x-auto rounded-lg border border-neutral-200">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-neutral-50 border-b border-neutral-200">
                          <th className="px-3 py-2 text-left text-xs font-semibold">Product</th>
                          <th className="px-3 py-2 text-right text-xs font-semibold">Qty</th>
                          <th className="px-3 py-2 text-right text-xs font-semibold">Unit Price</th>
                          <th className="px-3 py-2 text-right text-xs font-semibold">Disc %</th>
                          <th className="px-3 py-2 text-right text-xs font-semibold">GST %</th>
                          <th className="px-3 py-2 text-right text-xs font-semibold">Total</th>
                          <th className="px-3 py-2 text-right text-xs font-semibold">Received</th>
                        </tr>
                      </thead>
                      <tbody>
                        {poDetailItems.map((item, idx) => {
                          const product = products.find((p) => p.id === item.product_id);
                          const gross = (item.unit_price / 100) * item.quantity;
                          const disc = gross * (item.discount_percent || 0) / 100;
                          const taxable = gross - disc;
                          const total = taxable + taxable * item.gst_rate / 100;
                          return (
                            <tr key={idx} className="border-t border-neutral-100">
                              <td className="px-3 py-2 font-medium">{product?.name || 'Unknown'}</td>
                              <td className="px-3 py-2 text-right">{item.quantity}</td>
                              <td className="px-3 py-2 text-right">₹{(item.unit_price / 100).toFixed(2)}</td>
                              <td className="px-3 py-2 text-right">{item.discount_percent || 0}%</td>
                              <td className="px-3 py-2 text-right">{item.gst_rate}%</td>
                              <td className="px-3 py-2 text-right font-medium">₹{total.toFixed(2)}</td>
                              <td className="px-3 py-2 text-right">{item.received_quantity ?? 0} / {item.quantity}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* Actions */}
              <div className="flex gap-3">
                {selectedPO.status === 'draft' && (
                  <>
                    <button
                      onClick={handleSendPO}
                      disabled={sendMutation.isPending}
                      className="bg-primary text-white px-4 py-2 rounded-lg text-sm font-semibold hover:bg-primary/90 disabled:opacity-50"
                    >
                      {sendMutation.isPending ? 'Sending...' : 'Approve / Send'}
                    </button>
                    <button
                      onClick={handleCancelPO}
                      disabled={cancelPOMutation.isPending}
                      className="bg-red-50 text-red-600 border border-red-200 px-4 py-2 rounded-lg text-sm font-semibold hover:bg-red-100 disabled:opacity-50"
                    >
                      {cancelPOMutation.isPending ? 'Cancelling...' : 'Cancel PO'}
                    </button>
                  </>
                )}
                {(selectedPO.status === 'sent' || selectedPO.status === 'partial') && (
                  <button
                    onClick={() => {
                      setShowPODetail(false);
                      navigate('/purchase/grn?po_id=' + selectedPO.id);
                    }}
                    className="bg-secondary text-white px-4 py-2 rounded-lg text-sm font-semibold hover:bg-secondary/90"
                  >
                    <span className="inline-flex items-center gap-1"><span className="material-icons text-sm" aria-hidden="true">inventory_2</span>Create GRN</span>
                  </button>
                )}
              </div>

              <div className="flex justify-end">
                <button onClick={() => setShowPODetail(false)} className="rounded-lg border border-neutral-200 bg-white px-4 py-2 text-sm font-semibold hover:bg-neutral-50">
                  Close
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
};

export default PurchaseOrderPage;


