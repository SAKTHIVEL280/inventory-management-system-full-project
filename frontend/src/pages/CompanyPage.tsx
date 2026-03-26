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
  website: z.string().optional(),
  address_line1: z.string().optional(),
  address_line2: z.string().optional(),
  city: z.string().optional(),
  state: z.string().optional(),
  pincode: z.string().optional(),
  bank_name: z.string().optional(),
  bank_account_no: z.string().optional(),
  bank_ifsc: z.string().optional(),
  bank_branch: z.string().optional(),
});

type CompanyForm = z.infer<typeof schema>;

const normalizeOptional = (value?: string): string | null => {
  const trimmed = value?.trim();
  return trimmed ? trimmed : null;
};

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
      website: data?.website ?? '',
      address_line1: data?.address_line1 ?? '',
      address_line2: data?.address_line2 ?? '',
      city: data?.city ?? '',
      state: data?.state ?? '',
      pincode: data?.pincode ?? '',
      bank_name: data?.bank_name ?? '',
      bank_account_no: data?.bank_account_no ?? '',
      bank_ifsc: data?.bank_ifsc ?? '',
      bank_branch: data?.bank_branch ?? '',
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
        website: updated.website ?? '',
        address_line1: updated.address_line1 ?? '',
        address_line2: updated.address_line2 ?? '',
        city: updated.city ?? '',
        state: updated.state ?? '',
        pincode: updated.pincode ?? '',
        bank_name: updated.bank_name ?? '',
        bank_account_no: updated.bank_account_no ?? '',
        bank_ifsc: updated.bank_ifsc ?? '',
        bank_branch: updated.bank_branch ?? '',
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
      legal_name: normalizeOptional(parsed.data.legal_name),
      gstin: normalizeOptional(parsed.data.gstin)?.toUpperCase() ?? null,
      pan: normalizeOptional(parsed.data.pan)?.toUpperCase() ?? null,
      state_code: normalizeOptional(parsed.data.state_code)?.toUpperCase() ?? null,
      phone: normalizeOptional(parsed.data.phone),
      email: normalizeOptional(parsed.data.email),
      website: normalizeOptional(parsed.data.website),
      address_line1: normalizeOptional(parsed.data.address_line1),
      address_line2: normalizeOptional(parsed.data.address_line2),
      city: normalizeOptional(parsed.data.city),
      state: normalizeOptional(parsed.data.state),
      pincode: normalizeOptional(parsed.data.pincode),
      bank_name: normalizeOptional(parsed.data.bank_name),
      bank_account_no: normalizeOptional(parsed.data.bank_account_no),
      bank_ifsc: normalizeOptional(parsed.data.bank_ifsc)?.toUpperCase() ?? null,
      bank_branch: normalizeOptional(parsed.data.bank_branch),
    };
    mutation.mutate(payload);
  };

  return (
    <AppLayout title="Company Profile">
      {isLoading && <PageLoading message="Loading company profile..." />}
      {isError && <PageError message="Failed to load company profile" />}
      {!isLoading && !isError && (
        <form onSubmit={handleSubmit(onSubmit)}>
          <div className="space-y-6">
            {/* Basic Information */}
            <div className="hms-card p-6">
              <h2 className="font-display text-lg font-bold text-neutral-900 mb-4">Basic Information</h2>
              <p className="text-sm text-neutral-500 mb-4">This information will appear on all your invoices and documents.</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="company_name" className="hms-label">Company name *</label>
                  <input id="company_name" className="hms-input" {...register('name')} />
                </div>
                <div>
                  <label htmlFor="legal_name" className="hms-label">Legal name</label>
                  <input id="legal_name" className="hms-input" {...register('legal_name')} />
                </div>
                <div>
                  <label htmlFor="company_gstin" className="hms-label">GSTIN</label>
                  <input id="company_gstin" className="hms-input" placeholder="e.g. 33AABCT1234F1Z5" {...register('gstin')} />
                </div>
                <div>
                  <label htmlFor="company_pan" className="hms-label">PAN</label>
                  <input id="company_pan" className="hms-input" placeholder="e.g. AABCT1234F" {...register('pan')} />
                </div>
                <div>
                  <label htmlFor="state_code" className="hms-label">State code</label>
                  <input id="state_code" className="hms-input" placeholder="e.g. 33" {...register('state_code')} />
                </div>
                <div>
                  <label htmlFor="company_website" className="hms-label">Website</label>
                  <input id="company_website" className="hms-input" placeholder="https://" {...register('website')} />
                </div>
                <div>
                  <label htmlFor="company_phone" className="hms-label">Phone</label>
                  <input id="company_phone" className="hms-input" autoComplete="tel" {...register('phone')} />
                </div>
                <div>
                  <label htmlFor="company_email" className="hms-label">Email</label>
                  <input id="company_email" className="hms-input" autoComplete="email" {...register('email')} />
                </div>
              </div>
            </div>

            {/* Address */}
            <div className="hms-card p-6">
              <h2 className="font-display text-lg font-bold text-neutral-900 mb-4">Address</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="md:col-span-2">
                  <label htmlFor="address_line1" className="hms-label">Address line 1</label>
                  <input id="address_line1" className="hms-input" placeholder="Building, Street" {...register('address_line1')} />
                </div>
                <div className="md:col-span-2">
                  <label htmlFor="address_line2" className="hms-label">Address line 2</label>
                  <input id="address_line2" className="hms-input" placeholder="Area, Landmark" {...register('address_line2')} />
                </div>
                <div>
                  <label htmlFor="city" className="hms-label">City</label>
                  <input id="city" className="hms-input" {...register('city')} />
                </div>
                <div>
                  <label htmlFor="state" className="hms-label">State</label>
                  <input id="state" className="hms-input" {...register('state')} />
                </div>
                <div>
                  <label htmlFor="pincode" className="hms-label">Pincode</label>
                  <input id="pincode" className="hms-input" placeholder="e.g. 600001" {...register('pincode')} />
                </div>
              </div>
            </div>

            {/* Bank Details */}
            <div className="hms-card p-6">
              <h2 className="font-display text-lg font-bold text-neutral-900 mb-4">Bank Details</h2>
              <p className="text-sm text-neutral-500 mb-4">Bank details will be printed on your invoices for payment reference.</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="bank_name" className="hms-label">Bank name</label>
                  <input id="bank_name" className="hms-input" {...register('bank_name')} />
                </div>
                <div>
                  <label htmlFor="bank_branch" className="hms-label">Branch</label>
                  <input id="bank_branch" className="hms-input" {...register('bank_branch')} />
                </div>
                <div>
                  <label htmlFor="bank_account_no" className="hms-label">Account number</label>
                  <input id="bank_account_no" className="hms-input" {...register('bank_account_no')} />
                </div>
                <div>
                  <label htmlFor="bank_ifsc" className="hms-label">IFSC code</label>
                  <input id="bank_ifsc" className="hms-input" placeholder="e.g. SBIN0001234" {...register('bank_ifsc')} />
                </div>
              </div>
            </div>

            {/* Submit */}
            <div className="hms-card p-6">
              {formError && <p className="mb-4 text-sm text-danger" role="alert">{formError}</p>}
              {mutation.isError && <p className="mb-4 text-sm text-danger" role="alert">Failed to save company profile</p>}
              {mutation.isSuccess && <p className="mb-4 text-sm text-success" role="status">Company profile saved successfully</p>}
              <div className="flex justify-end">
                <button type="submit" disabled={mutation.isPending} className="rounded-lg bg-primary px-6 py-2.5 text-sm font-bold text-white shadow-lg shadow-primary/20 transition hover:bg-primary/90 disabled:opacity-60">
                  {mutation.isPending ? 'Saving...' : 'Save Company Profile'}
                </button>
              </div>
            </div>
          </div>
        </form>
      )}
    </AppLayout>
  );
};

export default CompanyPage;
