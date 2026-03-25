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
  phone: z.string().min(1, 'Phone required'),
  gstin: z.string().optional(),
});

type SupplierForm = z.infer<typeof schema>;

const SuppliersPage = () => {
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState('');

  const { data, isLoading, isError } = useQuery({
    queryKey: ['suppliers'],
    queryFn: suppliersApi.list,
  });

  const { register, handleSubmit, reset } = useForm<SupplierForm>({
    defaultValues: { company_name: '', phone: '', gstin: '' },
  });

  const createMutation = useMutation({
    mutationFn: (payload: Omit<Supplier, 'id'>) => suppliersApi.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['suppliers'] });
      reset();
      setFormError('');
    },
  });

  const onSubmit = (values: SupplierForm): void => {
    const parsed = schema.safeParse(values);
    if (!parsed.success) {
      setFormError(parsed.error.issues[0]?.message ?? 'Validation failed');
      return;
    }

    createMutation.mutate({
      ...parsed.data,
      supplier_code: '',
      contact_person: '',
      email: '',
      alternate_phone: '',
      pan: '',
      address_line1: '',
      address_line2: '',
      city: '',
      state: '',
      state_code: '',
      pincode: '',
      bank_name: '',
      bank_account_no: '',
      bank_ifsc: '',
      payment_terms_days: 30,
      opening_balance: 0,
      opening_balance_type: 'cr',
      is_active: true,
    });
  };

  const items = data?.items ?? [];

  return (
    <AppLayout title="Supplier Master">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="bg-white border border-neutral-200 rounded p-4">
          <h2 className="text-base font-semibold mb-3">New Supplier</h2>
          <form className="space-y-3" onSubmit={handleSubmit(onSubmit)}>
            <label htmlFor="supplier_company_name" className="text-sm text-neutral-700">Company name</label>
            <input id="supplier_company_name" className="w-full border border-neutral-300 rounded px-3 py-2" placeholder="Company name" {...register('company_name')} />
            <label htmlFor="supplier_phone" className="text-sm text-neutral-700">Phone</label>
            <input id="supplier_phone" className="w-full border border-neutral-300 rounded px-3 py-2" placeholder="Phone" autoComplete="tel" {...register('phone')} />
            <label htmlFor="supplier_gstin" className="text-sm text-neutral-700">GSTIN</label>
            <input id="supplier_gstin" className="w-full border border-neutral-300 rounded px-3 py-2" placeholder="GSTIN" {...register('gstin')} />
            {formError && <p className="text-sm text-danger" role="alert" aria-live="assertive">{formError}</p>}
            {createMutation.isError && <p className="text-sm text-danger" role="alert" aria-live="assertive">Failed to create supplier</p>}
            {createMutation.isSuccess && <p className="text-sm text-success" role="status" aria-live="polite">Supplier created successfully</p>}
            <button type="submit" disabled={createMutation.isPending} className="w-full bg-primary text-white rounded px-3 py-2">
              {createMutation.isPending ? 'Saving...' : 'Create Supplier'}
            </button>
          </form>
        </div>

        <div className="lg:col-span-2 bg-white border border-neutral-200 rounded p-4">
          <h2 className="text-base font-semibold mb-3">Suppliers</h2>
          {isLoading && <PageLoading message="Loading suppliers..." />}
          {isError && <PageError message="Failed to load suppliers" />}
          {!isLoading && !isError && items.length === 0 && <PageEmpty message="No suppliers found" />}
          {!isLoading && !isError && items.length > 0 && (
            <table className="w-full text-sm">
              <caption className="sr-only">Suppliers list</caption>
              <thead>
                <tr className="text-left border-b border-neutral-200">
                  <th scope="col" className="py-2">Code</th>
                  <th scope="col" className="py-2">Company</th>
                  <th scope="col" className="py-2">Phone</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id} className="border-b border-neutral-100">
                    <td className="py-2">{item.supplier_code}</td>
                    <td className="py-2">{item.company_name}</td>
                    <td className="py-2">{item.phone}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </AppLayout>
  );
};

export default SuppliersPage;
