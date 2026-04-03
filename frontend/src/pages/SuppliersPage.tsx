import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { suppliersApi } from '../api/suppliers';
import { Supplier } from '../types';
import { AppLayout } from '../components/AppLayout';
import { PageEmpty, PageError, PageLoading } from '../components/PageState';

const schema = z.object({
  company_name: z.string().min(1, 'Company name required'),
  phone: z.string().regex(/^[6-9]\d{9}$/, 'Must be a valid 10-digit Indian mobile number'),
  contact_person: z.string().optional(),
  email: z.string().email('Invalid email format').optional().or(z.literal('')),
  gstin: z.string().regex(/^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/i, 'Invalid GSTIN format').optional().or(z.literal('')),
  place_of_supply: z.string().optional(),
  payment_terms_days: z.coerce.number().min(0, 'Cannot be negative').default(30),
});

type SupplierForm = z.infer<typeof schema>;

const normalizeOptional = (value?: string): string | null => value?.trim() || null;

const SuppliersPage = () => {
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState('');
  const [editingItem, setEditingItem] = useState<Supplier | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['suppliers'],
    queryFn: suppliersApi.list,
  });

  const { register, handleSubmit, reset, setValue } = useForm<SupplierForm>({
    defaultValues: { company_name: '', phone: '', contact_person: '', email: '', gstin: '', place_of_supply: '', payment_terms_days: 30 },
  });

  const createMutation = useMutation({
    mutationFn: suppliersApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['suppliers'] });
      resetForm();
    },
    onError: (error: unknown) => {
      const axiosErr = error as any;
      const detail = axiosErr.response?.data?.detail;
      if (typeof detail === 'string') {
        setFormError(detail);
      } else if (Array.isArray(detail)) {
        setFormError(detail.map((d: any) => d.msg).join(', '));
      } else {
        setFormError('Failed to create supplier');
      }
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<Supplier> }) => suppliersApi.update(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['suppliers'] });
      resetForm();
    },
    onError: (error: unknown) => {
      const axiosErr = error as any;
      const detail = axiosErr.response?.data?.detail;
      if (typeof detail === 'string') {
        setFormError(detail);
      } else if (Array.isArray(detail)) {
        setFormError(detail.map((d: any) => d.msg).join(', '));
      } else {
        setFormError('Failed to update supplier');
      }
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => suppliersApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['suppliers'] });
      setDeleteConfirm(null);
      setFormError('');
    },
    onError: (error: unknown) => {
      const axiosErr = error as any;
      const detail = axiosErr.response?.data?.detail;
      if (typeof detail === 'string') {
        setFormError(detail);
      } else if (detail?.message) {
        // Handle backend error objects (e.g., outstanding balance errors)
        setFormError(detail.message);
      } else if (detail?.error_code === 'OUTSTANDING_EXISTS') {
        setFormError('Cannot delete supplier: There are outstanding payments. Please clear all dues before deleting.');
      } else if (Array.isArray(detail)) {
        setFormError(detail.map((d: any) => d.msg).join(', '));
      } else {
        setFormError('Failed to delete supplier');
      }
      setDeleteConfirm(null);
    },
  });

  const resetForm = () => {
    setEditingItem(null);
    setFormError('');
    reset({ company_name: '', phone: '', contact_person: '', email: '', gstin: '', place_of_supply: '', payment_terms_days: 30 });
  };

  const startEdit = (item: Supplier) => {
    setEditingItem(item);
    setFormError('');
    setValue('company_name', item.company_name);
    setValue('phone', item.phone);
    setValue('contact_person', item.contact_person ?? '');
    setValue('email', item.email ?? '');
    setValue('gstin', item.gstin ?? '');
    setValue('place_of_supply', item.place_of_supply ?? '');
    setValue('payment_terms_days', item.payment_terms_days ?? 30);
  };

  const onSubmit = (values: SupplierForm): void => {
    const parsed = schema.safeParse(values);
    if (!parsed.success) {
      setFormError(parsed.error.issues[0]?.message ?? 'Validation failed');
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
      address_line1: null,
      address_line2: null,
      city: null,
      state: null,
      state_code: null,
      pincode: null,
      bank_name: null,
      bank_account_no: null,
      bank_ifsc: null,
      place_of_supply: normalizeOptional(parsed.data.place_of_supply),
      payment_terms_days: parsed.data.payment_terms_days,
      opening_balance: editingItem?.opening_balance ?? 0,
      opening_balance_type: editingItem?.opening_balance_type ?? 'cr' as const,
      is_active: editingItem?.is_active ?? true,
    };

    if (editingItem) {
      updateMutation.mutate({ id: editingItem.id, payload });
    } else {
      createMutation.mutate({ ...payload, supplier_code: null });
    }
  };

  const items = data?.items ?? [];
  const isSaving = createMutation.isPending || updateMutation.isPending;

  return (
    <AppLayout title="Supplier Master">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="hms-card lg:col-span-1 p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-display text-lg font-bold text-neutral-900">
              {editingItem ? 'Modify/Change Supplier' : 'New Supplier'}
            </h2>
            {editingItem && (
              <button type="button" onClick={resetForm} className="text-sm text-neutral-500 hover:text-neutral-700">Cancel</button>
            )}
          </div>
          <form className="space-y-3" onSubmit={handleSubmit(onSubmit)}>
            <div>
              <label htmlFor="supplier_company_name" className="hms-label">Company name</label>
              <input id="supplier_company_name" className="hms-input" placeholder="Company name" {...register('company_name')} />
            </div>
            <div>
              <label htmlFor="supplier_contact" className="hms-label">Contact person</label>
              <input id="supplier_contact" className="hms-input" placeholder="Contact person" {...register('contact_person')} />
            </div>
            <div>
              <label htmlFor="supplier_phone" className="hms-label">Phone</label>
              <input id="supplier_phone" className="hms-input" placeholder="Phone" autoComplete="tel" {...register('phone')} />
            </div>
            <div>
              <label htmlFor="supplier_email" className="hms-label">Email</label>
              <input id="supplier_email" className="hms-input" placeholder="Email" autoComplete="email" {...register('email')} />
            </div>
            <div>
              <label htmlFor="supplier_gstin" className="hms-label">GSTIN</label>
              <input id="supplier_gstin" className="hms-input" placeholder="GSTIN" {...register('gstin')} />
            </div>
            <div>
              <label htmlFor="supplier_pos" className="hms-label">Place of Supply</label>
              <input id="supplier_pos" className="hms-input" placeholder="e.g. Tamil Nadu" {...register('place_of_supply')} />
            </div>
            <div>
              <label htmlFor="supplier_payment_terms" className="hms-label">Payment Terms (Days)</label>
              <input id="supplier_payment_terms" type="number" min="0" className="hms-input" placeholder="e.g. 30" {...register('payment_terms_days')} />
            </div>
            {formError && <p className="text-sm text-danger" role="alert" aria-live="assertive">{formError}</p>}
            {createMutation.isSuccess && <p className="text-sm text-success" role="status" aria-live="polite">Supplier created successfully</p>}
            {updateMutation.isSuccess && <p className="text-sm text-success" role="status" aria-live="polite">Supplier updated successfully</p>}
            <button type="submit" disabled={isSaving} className="w-full rounded-lg bg-primary px-5 py-2.5 text-sm font-bold text-white shadow-lg shadow-primary/20 transition hover:bg-primary/90 disabled:opacity-60">
              {isSaving ? 'Saving...' : editingItem ? 'Update Supplier' : 'Create Supplier'}
            </button>
          </form>
        </div>

        <div className="hms-card lg:col-span-2 overflow-hidden">
          <div className="border-b border-neutral-200 px-5 py-4">
            <h2 className="font-display text-lg font-bold text-neutral-900">Suppliers</h2>
          </div>
          <div className="p-5">
          {isLoading && <PageLoading message="Loading suppliers..." />}
          {isError && <PageError message="Failed to load suppliers" />}
          {!isLoading && !isError && items.length === 0 && <PageEmpty message="No suppliers found" />}
          {!isLoading && !isError && items.length > 0 && (
            <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <caption className="sr-only">Suppliers list</caption>
              <thead className="bg-neutral-50">
                <tr className="text-left border-y border-neutral-200">
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Code</th>
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Company</th>
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Phone</th>
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">GSTIN</th>
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {items.map((item) => (
                  <tr key={item.id} className="hover:bg-neutral-50/80">
                    <td className="px-4 py-3 font-mono text-xs">{item.supplier_code}</td>
                    <td className="px-4 py-3 font-medium">{item.company_name}</td>
                    <td className="px-4 py-3">{item.phone}</td>
                    <td className="px-4 py-3 font-mono text-xs">{item.gstin || '—'}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <button type="button" onClick={() => startEdit(item)} className="rounded px-2 py-1 text-xs font-semibold text-primary hover:bg-primary/10 transition">Modify/Change</button>
                        <button type="button" onClick={() => setDeleteConfirm(item.id)} className="rounded px-2 py-1 text-xs font-semibold text-danger hover:bg-red-50 transition">Delete</button>
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

      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
          <div className="hms-card w-full max-w-md space-y-6 p-6">
            <div>
              <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-red-100">
                <span className="material-icons text-red-600 text-2xl" aria-hidden="true">delete</span>
              </div>
              <h2 className="font-display text-lg font-bold text-neutral-900">Delete Supplier</h2>
              <p className="mt-2 text-sm text-neutral-600">Are you sure? This action cannot be undone.</p>
              
              {/* Error message for outstanding balance */}
              {formError && (
                <div className="mt-4 rounded-lg bg-red-50 border border-red-200 p-4">
                  <div className="flex items-start gap-3">
                    <span className="material-icons text-red-600 text-lg flex-shrink-0" aria-hidden="true">error</span>
                    <p className="text-sm text-red-800 font-medium">{formError}</p>
                  </div>
                </div>
              )}
            </div>
            <div className="flex gap-3">
              <button 
                type="button" 
                onClick={() => {
                  setDeleteConfirm(null);
                  setFormError('');
                }} 
                className="flex-1 rounded-lg border border-neutral-200 bg-white px-4 py-2.5 text-sm font-semibold text-neutral-600 transition hover:bg-neutral-50"
              >
                Cancel
              </button>
              <button 
                type="button" 
                onClick={() => deleteMutation.mutate(deleteConfirm)} 
                className="flex-1 rounded-lg bg-red-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-red-600/20 transition hover:bg-red-700"
              >
                <span className="material-icons text-sm align-middle mr-1">delete</span>
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </AppLayout>
  );
};

export default SuppliersPage;
