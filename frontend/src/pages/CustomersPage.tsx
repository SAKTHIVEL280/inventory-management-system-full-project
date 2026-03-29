import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { customersApi } from '../api/customers';
import { Customer } from '../types';
import { AppLayout } from '../components/AppLayout';
import { PageEmpty, PageError, PageLoading } from '../components/PageState';
import { showError, showSuccess, confirmDelete, confirmWithToast } from '../utils/toastHelper';

const schema = z.object({
  company_name: z.string().min(1, 'Company name required'),
  phone: z.string().regex(/^[6-9]\d{9}$/, 'Must be a valid 10-digit Indian mobile number'),
  customer_type: z.enum(['regular', 'dealer', 'distributor', 'retail']),
  contact_person: z.string().optional(),
  email: z.string().email('Invalid email format').optional().or(z.literal('')),
  gstin: z.string().regex(/^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/i, 'Invalid GSTIN format').optional().or(z.literal('')),
  billing_address_line1: z.string().optional(),
  billing_city: z.string().optional(),
  billing_state: z.string().optional(),
  billing_state_code: z.string().optional(),
  billing_pincode: z.string().optional(),
  same_as_billing: z.boolean().default(true),
});

type CustomerForm = z.infer<typeof schema>;

const normalizeOptional = (value?: string): string | null => value?.trim() || null;

const CustomersPage = () => {
  const queryClient = useQueryClient();
  const [editingItem, setEditingItem] = useState<Customer | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['customers'],
    queryFn: customersApi.list,
  });

  const { register, handleSubmit, reset, setValue } = useForm<CustomerForm>({
    defaultValues: { company_name: '', phone: '', customer_type: 'regular', contact_person: '', email: '', gstin: '', billing_address_line1: '', billing_city: '', billing_state: '', billing_state_code: '', billing_pincode: '', same_as_billing: true },
  });

  const createMutation = useMutation({
    mutationFn: customersApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customers'] });
      resetForm();
      showSuccess('Customer created successfully');
    },
    onError: (error: unknown) => {
      const axiosErr = error as any;
      const detail = axiosErr.response?.data?.detail;
      let errorMessage = 'Failed to create customer';
      
      if (typeof detail === 'string') {
        errorMessage = detail;
      } else if (Array.isArray(detail)) {
        errorMessage = detail.map((d: any) => d.msg).join(', ');
      } else if (detail?.message) {
        errorMessage = detail.message;
      }
      
      showError(errorMessage);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<Customer> }) => customersApi.update(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customers'] });
      resetForm();
      showSuccess('Customer updated successfully');
    },
    onError: (error: unknown) => {
      const axiosErr = error as any;
      const detail = axiosErr.response?.data?.detail;
      let errorMessage = 'Failed to update customer';
      
      if (typeof detail === 'string') {
        errorMessage = detail;
      } else if (Array.isArray(detail)) {
        errorMessage = detail.map((d: any) => d.msg).join(', ');
      } else if (detail?.message) {
        errorMessage = detail.message;
      }
      
      showError(errorMessage);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => customersApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customers'] });
    },
    onError: (error: unknown) => {
      const axiosErr = error as any;
      const detail = axiosErr.response?.data?.detail;
      let errorMessage = 'Failed to delete customer';

      if (typeof detail === 'string') {
        errorMessage = detail;
      } else if (detail?.message) {
        errorMessage = detail.message;
      } else if (detail?.error_code === 'OUTSTANDING_EXISTS') {
        errorMessage = 'Cannot delete customer: They have outstanding invoice balance. Please clear all dues before deleting.';
      } else if (Array.isArray(detail)) {
        errorMessage = detail.map((d: any) => d.msg).join(', ');
      }

      showError(errorMessage);
    },
  });

  const resetForm = () => {
    setEditingItem(null);
    reset({ company_name: '', phone: '', customer_type: 'regular', contact_person: '', email: '', gstin: '', billing_address_line1: '', billing_city: '', billing_state: '', billing_state_code: '', billing_pincode: '', same_as_billing: true });
  };

  const startEdit = (item: Customer) => {
    setEditingItem(item);
    setValue('company_name', item.company_name);
    setValue('phone', item.phone);
    setValue('customer_type', item.customer_type);
    setValue('contact_person', item.contact_person ?? '');
    setValue('email', item.email ?? '');
    setValue('gstin', item.gstin ?? '');
    setValue('billing_address_line1', item.billing_address_line1 ?? '');
    setValue('billing_city', item.billing_city ?? '');
    setValue('billing_state', item.billing_state ?? '');
    setValue('billing_state_code', item.billing_state_code ?? '');
    setValue('billing_pincode', item.billing_pincode ?? '');
    setValue('same_as_billing', item.same_as_billing ?? true);
  };

  const onSubmit = (values: CustomerForm): void => {
    const parsed = schema.safeParse(values);
    if (!parsed.success) {
      const errorMsg = parsed.error.issues[0]?.message ?? 'Validation failed';
      showError(errorMsg);
      return;
    }

    const payload = {
      company_name: parsed.data.company_name.trim(),
      contact_person: normalizeOptional(parsed.data.contact_person),
      email: normalizeOptional(parsed.data.email),
      phone: parsed.data.phone.trim(),
      alternate_phone: null,
      gstin: normalizeOptional(parsed.data.gstin)?.toUpperCase() ?? null,
      pan: null,
      customer_type: parsed.data.customer_type,
      billing_address_line1: normalizeOptional(parsed.data.billing_address_line1),
      billing_address_line2: null,
      billing_city: normalizeOptional(parsed.data.billing_city),
      billing_state: normalizeOptional(parsed.data.billing_state),
      billing_state_code: normalizeOptional(parsed.data.billing_state_code),
      billing_pincode: normalizeOptional(parsed.data.billing_pincode),
      shipping_address_line1: null,
      shipping_address_line2: null,
      shipping_city: null,
      shipping_state: null,
      shipping_state_code: null,
      shipping_pincode: null,
      same_as_billing: parsed.data.same_as_billing ?? true,
      credit_limit: editingItem?.credit_limit ?? 0,
      payment_terms_days: editingItem?.payment_terms_days ?? 30,
      opening_balance: editingItem?.opening_balance ?? 0,
      opening_balance_type: editingItem?.opening_balance_type ?? 'dr' as const,
      is_active: editingItem?.is_active ?? true,
    };

    if (editingItem) {
      confirmWithToast(
        `Are you sure you want to update customer "${editingItem.company_name}"?`,
        {
          onConfirm: () => updateMutation.mutate({ id: editingItem.id, payload }),
          type: 'confirm',
        }
      );
    } else {
      createMutation.mutate({ ...payload, customer_code: null });
    }
  };

  const items = data?.items ?? [];
  const isSaving = createMutation.isPending || updateMutation.isPending;

  return (
    <AppLayout title="Customer Master">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="hms-card lg:col-span-1 p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-display text-lg font-bold text-neutral-900">
              {editingItem ? 'Edit Customer' : 'New Customer'}
            </h2>
            {editingItem && (
              <button type="button" onClick={resetForm} className="text-sm text-neutral-500 hover:text-neutral-700">
                Cancel
              </button>
            )}
          </div>
          <form className="space-y-3" onSubmit={handleSubmit(onSubmit)}>
            <div>
              <label htmlFor="company_name" className="hms-label">Company name</label>
              <input id="company_name" className="hms-input" placeholder="Company name" {...register('company_name')} />
            </div>
            <div>
              <label htmlFor="contact_person" className="hms-label">Contact person</label>
              <input id="contact_person" className="hms-input" placeholder="Contact person" {...register('contact_person')} />
            </div>
            <div>
              <label htmlFor="phone" className="hms-label">Phone</label>
              <input id="phone" type="tel" pattern="[6-9][0-9]{9}" title="10-digit mobile number starting with 6-9" className="hms-input" placeholder="e.g. 9876543210" autoComplete="tel" {...register('phone')} />
              <p className="mt-1 text-xs text-neutral-500">10-digit Indian mobile number</p>
            </div>
            <div>
              <label htmlFor="cust_email" className="hms-label">Email</label>
              <input id="cust_email" className="hms-input" placeholder="Email" autoComplete="email" {...register('email')} />
            </div>
            <div>
              <label htmlFor="gstin" className="hms-label">GSTIN</label>
              <input id="gstin" className="hms-input" placeholder="GSTIN" {...register('gstin')} />
            </div>
            <div>
              <label htmlFor="customer_type" className="hms-label">Customer type</label>
              <select id="customer_type" className="hms-input" {...register('customer_type')}>
                <option value="regular">Regular</option>
                <option value="dealer">Dealer</option>
                <option value="distributor">Distributor</option>
                <option value="retail">Retail</option>
              </select>
            </div>

            {/* BUG-30: Address fields */}
            <div className="pt-2 border-t border-neutral-100">
              <p className="text-xs font-bold uppercase tracking-wider text-neutral-500 mb-2">Billing Address</p>
            </div>
            <div>
              <label htmlFor="billing_address_line1" className="hms-label">Address</label>
              <input id="billing_address_line1" className="hms-input" placeholder="Address line 1" {...register('billing_address_line1')} />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label htmlFor="billing_city" className="hms-label">City</label>
                <input id="billing_city" className="hms-input" placeholder="City" {...register('billing_city')} />
              </div>
              <div>
                <label htmlFor="billing_state" className="hms-label">State</label>
                <input id="billing_state" className="hms-input" placeholder="State" {...register('billing_state')} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label htmlFor="billing_state_code" className="hms-label">State Code</label>
                <input id="billing_state_code" className="hms-input" placeholder="e.g. 29" maxLength={2} {...register('billing_state_code')} />
              </div>
              <div>
                <label htmlFor="billing_pincode" className="hms-label">Pincode</label>
                <input id="billing_pincode" className="hms-input" placeholder="Pincode" {...register('billing_pincode')} />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <input id="same_as_billing" type="checkbox" className="rounded border-neutral-300" {...register('same_as_billing')} />
              <label htmlFor="same_as_billing" className="text-sm text-neutral-600">Shipping same as billing</label>
            </div>
            <button type="submit" disabled={isSaving} className="w-full rounded-lg bg-primary px-5 py-2.5 text-sm font-bold text-white shadow-lg shadow-primary/20 transition hover:bg-primary/90 disabled:opacity-60">
              {isSaving ? 'Saving...' : editingItem ? 'Update Customer' : 'Create Customer'}
            </button>
          </form>
        </div>

        <div className="hms-card lg:col-span-2 overflow-hidden">
          <div className="border-b border-neutral-200 px-5 py-4">
            <h2 className="font-display text-lg font-bold text-neutral-900">Customers</h2>
          </div>
          <div className="p-5">
          {isLoading && <PageLoading message="Loading customers..." />}
          {isError && <PageError message="Failed to load customers" />}
          {!isLoading && !isError && items.length === 0 && <PageEmpty message="No customers found" />}
          {!isLoading && !isError && items.length > 0 && (
            <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <caption className="sr-only">Customers list</caption>
              <thead className="bg-neutral-50">
                <tr className="text-left border-y border-neutral-200">
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Code</th>
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Company</th>
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Phone</th>
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Type</th>
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {items.map((item) => (
                  <tr key={item.id} className="hover:bg-neutral-50/80">
                    <td className="px-4 py-3 font-mono text-xs">{item.customer_code}</td>
                    <td className="px-4 py-3 font-medium">{item.company_name}</td>
                    <td className="px-4 py-3">{item.phone}</td>
                    <td className="px-4 py-3">
                      <span className="rounded-full bg-blue-100 px-2.5 py-1 text-xs font-bold uppercase tracking-wide text-blue-700">
                        {item.customer_type}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <button 
                          type="button" 
                          onClick={() => startEdit(item)} 
                          className="rounded px-2 py-1 text-xs font-semibold text-primary hover:bg-primary/10 transition"
                        >
                          Edit
                        </button>
                        <button 
                          type="button" 
                          onClick={() => {
                            const customerName = item.company_name;
                            confirmDelete(customerName, () => deleteMutation.mutate(item.id));
                          }} 
                          className="rounded px-2 py-1 text-xs font-semibold text-danger hover:bg-red-50 transition"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          )}
          </div>
        </div>
      </div>

    </AppLayout>
  );
};

export default CustomersPage;
