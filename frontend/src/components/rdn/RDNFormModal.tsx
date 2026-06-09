import { createPortal } from 'react-dom';
import { useEffect, useMemo } from 'react';
import { useFieldArray, useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';
import { customersApi } from '../../api/customers';
import { productsApi } from '../../api/products';
import { salesApi, type SalesInvoiceItem } from '../../api/sales';
import { rdnApi } from '../../api/rdn';
import { todayLocalDateInputValue } from '../../utils/date';
import type { RDNCreatePayload, RDNDetailResponse, RDNReturnReasonOption } from '../../types';

const rdnItemSchema = z.object({
  invoice_item_id: z.string().min(1, 'Invoice item is required'),
  product_id: z.string().min(1, 'Product is required'),
  batch_no: z.string().min(1, 'Batch number is required'),
  manufacture_date: z.string().min(1, 'MFG date is required'),
  expiry_date: z.string().min(1, 'EXP date is required'),
  return_quantity: z.coerce.number().positive('Return quantity must be greater than 0'),
  reason_code: z.string().min(1, 'Reason is required'),
});

const rdnSchema = z.object({
  customer_id: z.string().min(1, 'Customer is required'),
  sales_invoice_id: z.string().min(1, 'Invoice is required'),
  customer_delivery_number: z.string().optional().nullable(),
  customer_delivery_date: z.string().min(1, 'Customer delivery date is required'),
  receipt_date: z.string().min(1, 'Receipt date is required'),
  notes: z.string().optional().nullable(),
  items: z.array(rdnItemSchema).min(1, 'Add at least one item'),
});

type RDNFormValues = z.infer<typeof rdnSchema>;

interface RDNFormModalProps {
  open: boolean;
  initialData?: RDNDetailResponse | null;
  onClose: () => void;
  onSaved: () => void;
}

const formatAmount = (paise?: number | null) => {
  if (!paise) return 'Rs. 0.00';
  return `Rs. ${(paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
};

export const RDNFormModal = ({ open, initialData, onClose, onSaved }: RDNFormModalProps) => {
  const isEditing = Boolean(initialData?.rdn);
  const form = useForm<RDNFormValues>({
    resolver: zodResolver(rdnSchema),
    defaultValues: {
      customer_id: '',
      sales_invoice_id: '',
      customer_delivery_number: '',
      customer_delivery_date: todayLocalDateInputValue(),
      receipt_date: todayLocalDateInputValue(),
      notes: '',
      items: [],
    },
  });

  const { control, register, handleSubmit, watch, setValue, reset, formState } = form;
  const { fields, append, remove, replace } = useFieldArray({ control, name: 'items' });

  const customerId = watch('customer_id');
  const invoiceId = watch('sales_invoice_id');

  const customersQuery = useQuery({
    queryKey: ['rdn-customers'],
    queryFn: () => customersApi.list({ page: 1, page_size: 500 }),
    enabled: open,
  });

  const invoicesQuery = useQuery({
    queryKey: ['rdn-invoices'],
    queryFn: () => salesApi.listInvoices(undefined, 1, 500),
    enabled: open,
  });

  const productsQuery = useQuery({
    queryKey: ['rdn-products'],
    queryFn: () => productsApi.listAll(),
    enabled: open,
  });

  const reasonsQuery = useQuery({
    queryKey: ['rdn-reasons'],
    queryFn: () => rdnApi.getCustomizationOptions(),
    enabled: open,
  });

  const invoiceDetailQuery = useQuery({
    queryKey: ['rdn-invoice-detail', invoiceId],
    queryFn: () => salesApi.getInvoice(invoiceId!),
    enabled: Boolean(invoiceId),
  });

  const productMap = useMemo(() => {
    const items = productsQuery.data?.items || [];
    return new Map(items.map((item) => [item.id, item]));
  }, [productsQuery.data?.items]);

  const reasons = (reasonsQuery.data?.return_reasons || []) as RDNReturnReasonOption[];

  const invoiceItems = (invoiceDetailQuery.data?.data?.items || []) as SalesInvoiceItem[];

  const invoiceItemMap = useMemo(() => {
    return new Map(invoiceItems.map((item) => [item.id, item]));
  }, [invoiceItems]);

  const invoiceOptions = useMemo(() => {
    const invoices = invoicesQuery.data?.data?.items || [];
    return invoices.filter((invoice) => {
      if (!customerId) return invoice.status !== 'draft' && invoice.status !== 'cancelled';
      return invoice.customer_id === customerId && invoice.status !== 'draft' && invoice.status !== 'cancelled';
    });
  }, [customerId, invoicesQuery.data?.data?.items]);

  useEffect(() => {
    if (!open) return;
    if (!isEditing) {
      reset({
        customer_id: '',
        sales_invoice_id: '',
        customer_delivery_number: '',
        customer_delivery_date: todayLocalDateInputValue(),
        receipt_date: todayLocalDateInputValue(),
        notes: '',
        items: [],
      });
    }
  }, [open, isEditing, reset]);

  useEffect(() => {
    if (!initialData?.rdn) return;
    const payload: RDNFormValues = {
      customer_id: initialData.rdn.customer_id,
      sales_invoice_id: initialData.rdn.sales_invoice_id,
      customer_delivery_number: initialData.rdn.customer_delivery_number || '',
      customer_delivery_date: initialData.rdn.customer_delivery_date,
      receipt_date: initialData.rdn.receipt_date,
      notes: initialData.rdn.notes || '',
      items: initialData.items.map((item) => ({
        invoice_item_id: item.invoice_item_id,
        product_id: item.product_id,
        batch_no: item.batch_no,
        manufacture_date: item.manufacture_date,
        expiry_date: item.expiry_date,
        return_quantity: item.return_quantity,
        reason_code: item.reason_code,
      })),
    };
    reset(payload);
  }, [initialData, reset]);

  useEffect(() => {
    if (!isEditing) {
      replace([]);
    }
  }, [invoiceId, isEditing, replace]);

  const handleInvoiceItemChange = (index: number, invoiceItemId: string) => {
    const invoiceItem = invoiceItemMap.get(invoiceItemId);
    setValue(`items.${index}.invoice_item_id`, invoiceItemId);
    setValue(`items.${index}.product_id`, invoiceItem?.product_id || '');
    if (invoiceItem?.batch_no) setValue(`items.${index}.batch_no`, invoiceItem.batch_no);
    if (invoiceItem?.manufacture_date) setValue(`items.${index}.manufacture_date`, invoiceItem.manufacture_date);
    if (invoiceItem?.expiry_date) setValue(`items.${index}.expiry_date`, invoiceItem.expiry_date);
  };

  const onSubmit = async (values: RDNFormValues) => {
    const payload: RDNCreatePayload = {
      ...values,
      items: values.items.map((item) => ({
        ...item,
        return_quantity: Number(item.return_quantity),
      })),
    };
    try {
      if (initialData?.rdn) {
        await rdnApi.update(initialData.rdn.id, payload);
        toast.success('RDN updated successfully');
      } else {
        await rdnApi.create(payload);
        toast.success('RDN created successfully');
      }
      onSaved();
      onClose();
    } catch (error) {
      console.error('Failed to save RDN', error);
      toast.error('Failed to save RDN');
    }
  };

  if (!open) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4">
      <form onSubmit={handleSubmit(onSubmit)} className="w-full max-w-6xl rounded-xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-neutral-200 px-6 py-4">
          <h2 className="text-lg font-bold text-neutral-900">{isEditing ? 'Edit RDN' : 'Create RDN'}</h2>
          <button type="button" onClick={onClose} className="text-neutral-500 hover:text-neutral-700">X</button>
        </div>

        <div className="grid gap-4 px-6 py-4 md:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-semibold">Customer *</label>
            <select className="hms-input" disabled={isEditing} {...register('customer_id')}>
              <option value="">Select customer</option>
              {(customersQuery.data?.items || []).map((customer) => (
                <option key={customer.id} value={customer.id}>{customer.company_name}</option>
              ))}
            </select>
            {formState.errors.customer_id && <p className="mt-1 text-xs text-red-500">{formState.errors.customer_id.message}</p>}
          </div>
          <div>
            <label className="mb-1 block text-sm font-semibold">Linked Sales Invoice *</label>
            <select className="hms-input" disabled={!customerId || isEditing} {...register('sales_invoice_id')}>
              <option value="">Select invoice</option>
              {invoiceOptions.map((invoice) => (
                <option key={invoice.id} value={invoice.id}>{invoice.invoice_number}</option>
              ))}
            </select>
            {formState.errors.sales_invoice_id && <p className="mt-1 text-xs text-red-500">{formState.errors.sales_invoice_id.message}</p>}
          </div>
          <div>
            <label className="mb-1 block text-sm font-semibold">Customer Delivery Number</label>
            <input className="hms-input" {...register('customer_delivery_number')} />
          </div>
          <div>
            <label className="mb-1 block text-sm font-semibold">Customer Delivery Date *</label>
            <input type="date" className="hms-input" {...register('customer_delivery_date')} />
            {formState.errors.customer_delivery_date && <p className="mt-1 text-xs text-red-500">{formState.errors.customer_delivery_date.message}</p>}
          </div>
          <div>
            <label className="mb-1 block text-sm font-semibold">Receipt Date *</label>
            <input type="date" className="hms-input" {...register('receipt_date')} />
            {formState.errors.receipt_date && <p className="mt-1 text-xs text-red-500">{formState.errors.receipt_date.message}</p>}
          </div>
          <div>
            <label className="mb-1 block text-sm font-semibold">Notes</label>
            <input className="hms-input" {...register('notes')} />
          </div>
        </div>

        <div className="px-6 pb-2">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-neutral-700">Item Details</h3>
            <button type="button" onClick={() => append({
              invoice_item_id: '',
              product_id: '',
              batch_no: '',
              manufacture_date: '',
              expiry_date: '',
              return_quantity: '',
              reason_code: '',
            })} className="rounded-lg border border-neutral-200 px-3 py-1.5 text-sm font-semibold text-neutral-600">
              Add Item
            </button>
          </div>
        </div>

        <div className="px-6 pb-6">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-neutral-200 bg-neutral-50">
                  <th className="w-64 px-3 py-2 text-left font-semibold">Invoice Item</th>
                  <th className="w-48 px-3 py-2 text-left font-semibold">Product</th>
                  <th className="px-3 py-2 text-right font-semibold">Invoice Qty</th>
                  <th className="px-3 py-2 text-right font-semibold">Return Qty</th>
                  <th className="px-3 py-2 text-left font-semibold">Batch No</th>
                  <th className="px-3 py-2 text-left font-semibold">MFG</th>
                  <th className="px-3 py-2 text-left font-semibold">EXP</th>
                  <th className="px-3 py-2 text-right font-semibold">MRP</th>
                  <th className="px-3 py-2 text-left font-semibold">Reason</th>
                  <th className="px-3 py-2 text-center font-semibold"></th>
                </tr>
              </thead>
              <tbody>
                {fields.length === 0 ? (
                  <tr>
                    <td colSpan={10} className="px-3 py-6 text-center text-neutral-400">No items added</td>
                  </tr>
                ) : (
                  fields.map((field, index) => {
                    const invoiceItem = invoiceItemMap.get(watch(`items.${index}.invoice_item_id`));
                    const product = productMap.get(watch(`items.${index}.product_id`));
                    return (
                      <tr key={field.id} className="border-b border-neutral-100">
                        <td className="px-3 py-2">
                          <select
                            className="h-9 w-full min-w-[260px] rounded border px-2 text-sm"
                            value={watch(`items.${index}.invoice_item_id`)}
                            onChange={(event) => handleInvoiceItemChange(index, event.target.value)}
                            disabled={!invoiceId}
                          >
                            <option value="">Select</option>
                            {invoiceItems.map((item) => (
                              <option key={item.id} value={item.id}>
                                {item.description || productMap.get(item.product_id)?.name || item.id.slice(0, 8)}
                              </option>
                            ))}
                          </select>
                          {formState.errors.items?.[index]?.invoice_item_id && (
                            <p className="mt-1 text-xs text-red-500">{formState.errors.items[index]?.invoice_item_id?.message}</p>
                          )}
                        </td>
                        <td className="px-3 py-2">
                          <span className="block min-w-[180px]">{product?.name || '-'}</span>
                        </td>
                        <td className="px-3 py-2 text-right">{invoiceItem?.quantity ?? '-'}</td>
                        <td className="px-3 py-2 text-right">
                          <input type="number" step="0.01" className="h-9 w-24 rounded border px-2 text-sm text-right" {...register(`items.${index}.return_quantity`)} />
                        </td>
                        <td className="px-3 py-2">
                          <input className="h-9 w-28 rounded border px-2 text-sm" {...register(`items.${index}.batch_no`)} />
                        </td>
                        <td className="px-3 py-2">
                          <input type="date" className="h-9 w-36 rounded border px-2 text-sm" {...register(`items.${index}.manufacture_date`)} />
                        </td>
                        <td className="px-3 py-2">
                          <input type="date" className="h-9 w-36 rounded border px-2 text-sm" {...register(`items.${index}.expiry_date`)} />
                        </td>
                        <td className="px-3 py-2 text-right text-amber-700 font-semibold">{formatAmount(product?.mrp)}</td>
                        <td className="px-3 py-2">
                          <select className="h-9 w-40 rounded border px-2 text-sm" {...register(`items.${index}.reason_code`)}>
                            <option value="">Select</option>
                            {reasons.map((reason) => (
                              <option key={reason.value} value={reason.value}>{reason.label}</option>
                            ))}
                          </select>
                        </td>
                        <td className="px-3 py-2 text-center">
                          <button type="button" onClick={() => remove(index)} className="text-red-500">Remove</button>
                        </td>
                        <input type="hidden" {...register(`items.${index}.product_id`)} />
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
          {formState.errors.items?.message && (
            <p className="mt-2 text-xs text-red-500">{formState.errors.items.message}</p>
          )}
        </div>

        <div className="flex justify-end gap-3 border-t border-neutral-200 px-6 py-4">
          <button type="button" onClick={onClose} className="rounded-lg border border-neutral-200 px-4 py-2 text-sm font-semibold text-neutral-600">Cancel</button>
          <button type="submit" className="rounded-lg bg-primary px-6 py-2 text-sm font-semibold text-white">{isEditing ? 'Update' : 'Create'}</button>
        </div>
      </form>
    </div>,
    document.body
  );
};
