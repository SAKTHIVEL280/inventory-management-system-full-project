import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { companyApi } from '../api/company';
import { Company } from '../types';
import { AppLayout } from '../components/AppLayout';
import { PageError, PageLoading } from '../components/PageState';

const schema = z.object({
  name: z.string().min(1, 'Company name is required'),
  legal_name: z.string().optional(),
  gstin: z.string().optional(),
  pan: z.string().optional(),
  state_code: z.string().optional(),
  phone: z.string().optional(),
  email: z.string().optional(),
});

type CompanyForm = z.infer<typeof schema>;

const emptyCompany: Company = {
  name: '',
  invoice_prefix: 'INV',
  invoice_counter: 1,
  po_prefix: 'PO',
  po_counter: 1,
  so_prefix: 'SO',
  so_counter: 1,
  qtn_prefix: 'QTN',
  qtn_counter: 1,
  grn_prefix: 'GRN',
  grn_counter: 1,
};

const CompanyPage = () => {
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState('');

  const { data, isLoading, isError } = useQuery({
    queryKey: ['company'],
    queryFn: companyApi.get,
  });

  const { register, handleSubmit, reset } = useForm<CompanyForm>({
    values: {
      name: data?.name ?? '',
      legal_name: data?.legal_name ?? '',
      gstin: data?.gstin ?? '',
      pan: data?.pan ?? '',
      state_code: data?.state_code ?? '',
      phone: data?.phone ?? '',
      email: data?.email ?? '',
    },
  });

  const mutation = useMutation({
    mutationFn: (payload: Company) => companyApi.update(payload),
    onSuccess: (updated) => {
      queryClient.setQueryData(['company'], updated);
      reset({
        name: updated.name,
        legal_name: updated.legal_name ?? '',
        gstin: updated.gstin ?? '',
        pan: updated.pan ?? '',
        state_code: updated.state_code ?? '',
        phone: updated.phone ?? '',
        email: updated.email ?? '',
      });
      setFormError('');
    },
  });

  const onSubmit = (values: CompanyForm): void => {
    const parsed = schema.safeParse(values);
    if (!parsed.success) {
      setFormError(parsed.error.issues[0]?.message ?? 'Validation failed');
      return;
    }

    const payload: Company = {
      ...(data ?? emptyCompany),
      ...parsed.data,
    };
    mutation.mutate(payload);
  };

  return (
    <AppLayout title="Company Profile">
      {isLoading && <PageLoading message="Loading company profile..." />}
      {isError && <PageError message="Failed to load company profile" />}
      {!isLoading && !isError && (
        <div className="hms-card p-6">
          <form className="grid grid-cols-1 md:grid-cols-2 gap-4" onSubmit={handleSubmit(onSubmit)}>
            <label className="text-sm text-neutral-700">
              Company name
              <input id="company_name" className="hms-input mt-1" {...register('name')} />
            </label>
            <label className="text-sm text-neutral-700">
              Legal name
              <input id="legal_name" className="hms-input mt-1" {...register('legal_name')} />
            </label>
            <label className="text-sm text-neutral-700">
              GSTIN
              <input id="company_gstin" className="hms-input mt-1" {...register('gstin')} />
            </label>
            <label className="text-sm text-neutral-700">
              PAN
              <input id="company_pan" className="hms-input mt-1" {...register('pan')} />
            </label>
            <label className="text-sm text-neutral-700">
              State code
              <input id="state_code" className="hms-input mt-1" {...register('state_code')} />
            </label>
            <label className="text-sm text-neutral-700">
              Phone
              <input id="company_phone" className="hms-input mt-1" autoComplete="tel" {...register('phone')} />
            </label>
            <label className="text-sm text-neutral-700 md:col-span-2">
              Email
              <input id="company_email" className="hms-input mt-1" autoComplete="email" {...register('email')} />
            </label>

            {formError && <p className="md:col-span-2 text-sm text-danger" role="alert" aria-live="assertive">{formError}</p>}
            {mutation.isError && <p className="md:col-span-2 text-sm text-danger" role="alert" aria-live="assertive">Failed to save company profile</p>}
            {mutation.isSuccess && <p className="md:col-span-2 text-sm text-success" role="status" aria-live="polite">Company profile saved</p>}

            <div className="md:col-span-2 flex justify-end">
              <button type="submit" disabled={mutation.isPending} className="rounded-lg bg-primary px-5 py-2.5 text-sm font-bold text-white shadow-lg shadow-primary/20 transition hover:bg-primary/90 disabled:opacity-60">
                {mutation.isPending ? 'Saving...' : 'Save Company'}
              </button>
            </div>
          </form>
        </div>
      )}
    </AppLayout>
  );
};

export default CompanyPage;
