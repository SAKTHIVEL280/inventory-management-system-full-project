import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { customersApi } from '../api/customers';
import { Customer } from '../types';
import { AppLayout } from '../components/AppLayout';
import { PageEmpty, PageError, PageLoading } from '../components/PageState';

const schema = z.object({
  company_name: z.string().min(1, 'Company name required'),
  phone: z.string().min(1, 'Phone required'),
  customer_type: z.enum(['regular', 'dealer', 'distributor', 'retail']),
  gstin: z.string().optional(),
});

type CustomerForm = z.infer<typeof schema>;

const CustomersPage = () => {
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState('');

  const { data, isLoading, isError } = useQuery({
    queryKey: ['customers'],
    queryFn: customersApi.list,
  });

  const { register, handleSubmit, reset } = useForm<CustomerForm>({
    defaultValues: { company_name: '', phone: '', customer_type: 'regular', gstin: '' },
  });

  const createMutation = useMutation({
    mutationFn: (payload: Omit<Customer, 'id'>) => customersApi.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customers'] });
      reset();
      setFormError('');
    },
  });

  const onSubmit = (values: CustomerForm): void => {
    const parsed = schema.safeParse(values);
    if (!parsed.success) {
      setFormError(parsed.error.issues[0]?.message ?? 'Validation failed');
      return;
    }

    createMutation.mutate({
      ...parsed.data,
      customer_code: '',
      contact_person: '',
      email: '',
      alternate_phone: '',
      pan: '',
      billing_address_line1: '',
      billing_address_line2: '',
      billing_city: '',
      billing_state: '',
      billing_state_code: '',
      billing_pincode: '',
      shipping_address_line1: '',
      shipping_address_line2: '',
      shipping_city: '',
      shipping_state: '',
      shipping_state_code: '',
      shipping_pincode: '',
      same_as_billing: true,
      credit_limit: 0,
      payment_terms_days: 30,
      opening_balance: 0,
      opening_balance_type: 'dr',
      is_active: true,
    });
  };

  const items = data?.items ?? [];

  return (
    <AppLayout title="Customer Master">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="bg-white border border-neutral-200 rounded p-4">
          <h2 className="text-base font-semibold mb-3">New Customer</h2>
          <form className="space-y-3" onSubmit={handleSubmit(onSubmit)}>
            <label htmlFor="company_name" className="text-sm text-neutral-700">Company name</label>
            <input id="company_name" className="w-full border border-neutral-300 rounded px-3 py-2" placeholder="Company name" {...register('company_name')} />
            <label htmlFor="phone" className="text-sm text-neutral-700">Phone</label>
            <input id="phone" className="w-full border border-neutral-300 rounded px-3 py-2" placeholder="Phone" autoComplete="tel" {...register('phone')} />
            <label htmlFor="gstin" className="text-sm text-neutral-700">GSTIN</label>
            <input id="gstin" className="w-full border border-neutral-300 rounded px-3 py-2" placeholder="GSTIN" {...register('gstin')} />
            <label htmlFor="customer_type" className="text-sm text-neutral-700">Customer type</label>
            <select id="customer_type" className="w-full border border-neutral-300 rounded px-3 py-2" {...register('customer_type')}>
              <option value="regular">Regular</option>
              <option value="dealer">Dealer</option>
              <option value="distributor">Distributor</option>
              <option value="retail">Retail</option>
            </select>
            {formError && <p className="text-sm text-danger" role="alert" aria-live="assertive">{formError}</p>}
            {createMutation.isError && <p className="text-sm text-danger" role="alert" aria-live="assertive">Failed to create customer</p>}
            {createMutation.isSuccess && <p className="text-sm text-success" role="status" aria-live="polite">Customer created successfully</p>}
            <button type="submit" disabled={createMutation.isPending} className="w-full bg-primary text-white rounded px-3 py-2">
              {createMutation.isPending ? 'Saving...' : 'Create Customer'}
            </button>
          </form>
        </div>

        <div className="lg:col-span-2 bg-white border border-neutral-200 rounded p-4">
          <h2 className="text-base font-semibold mb-3">Customers</h2>
          {isLoading && <PageLoading message="Loading customers..." />}
          {isError && <PageError message="Failed to load customers" />}
          {!isLoading && !isError && items.length === 0 && <PageEmpty message="No customers found" />}
          {!isLoading && !isError && items.length > 0 && (
            <table className="w-full text-sm">
              <caption className="sr-only">Customers list</caption>
              <thead>
                <tr className="text-left border-b border-neutral-200">
                  <th scope="col" className="py-2">Code</th>
                  <th scope="col" className="py-2">Company</th>
                  <th scope="col" className="py-2">Phone</th>
                  <th scope="col" className="py-2">Type</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id} className="border-b border-neutral-100">
                    <td className="py-2">{item.customer_code}</td>
                    <td className="py-2">{item.company_name}</td>
                    <td className="py-2">{item.phone}</td>
                    <td className="py-2 capitalize">{item.customer_type}</td>
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

export default CustomersPage;
