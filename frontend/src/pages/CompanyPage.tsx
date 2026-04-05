import { useRef } from 'react';
import { useForm } from 'react-hook-form';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { companyApi } from '../api/company';
import { Company } from '../types';
import { AppLayout } from '../components/AppLayout';
import { PageError, PageLoading } from '../components/PageState';
import { getStaticUrl } from '../utils/url_utils';
import { getApiDetail, getApiDetailMessage } from '../utils/apiError';
import { showError, showSuccess } from '../utils/toastHelper';

const schema = z.object({
  name: z.string().min(1, 'Company name is required'),
  legal_name: z.string().optional(),
  gstin: z.string().optional(),
  gstin_status: z.string().optional(),
  pan: z.string().optional(),
  company_director_name: z.string().optional(),
  company_director_contact: z.string().optional(),
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
  account_holder_name: z.string().optional(),
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
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['company'],
    queryFn: companyApi.get,
  });

  const { register, handleSubmit, reset, watch } = useForm<CompanyForm>({
    values: {
      name: data?.name ?? '',
      legal_name: data?.legal_name ?? '',
      gstin: data?.gstin ?? '',
      gstin_status: data?.gstin_status ?? 'non-registered',
      pan: data?.pan ?? '',
      company_director_name: data?.company_director_name ?? '',
      company_director_contact: data?.company_director_contact ?? '',
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
      account_holder_name: data?.account_holder_name ?? '',
      bank_account_no: data?.bank_account_no ?? '',
      bank_ifsc: data?.bank_ifsc ?? '',
      bank_branch: data?.bank_branch ?? '',
    },
  });

  const gstin_status = watch('gstin_status');

  const mutation = useMutation({
    mutationFn: (payload: Company) => companyApi.update(payload),
    onSuccess: (updated) => {
      queryClient.setQueryData(['company'], updated);
      queryClient.setQueryData(['company-branding'], (old: { name?: string; logo_url?: string | null } | undefined) => ({
        name: updated.name,
        logo_url: updated.logo_url ?? old?.logo_url ?? null,
      }));
      reset({
        name: updated.name,
        legal_name: updated.legal_name ?? '',
        gstin: updated.gstin ?? '',
        gstin_status: updated.gstin_status ?? 'non-registered',
        pan: updated.pan ?? '',
        company_director_name: updated.company_director_name ?? '',
        company_director_contact: updated.company_director_contact ?? '',
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
        account_holder_name: updated.account_holder_name ?? '',
        bank_account_no: updated.bank_account_no ?? '',
        bank_ifsc: updated.bank_ifsc ?? '',
        bank_branch: updated.bank_branch ?? '',
      });
      showSuccess('Company profile saved successfully');
    },
    onError: (error: unknown) => {
      const detail = getApiDetail(error);
      showError(getApiDetailMessage(detail, 'Failed to save company profile'));
    },
  });

  const logoMutation = useMutation({
    mutationFn: companyApi.uploadLogo,
    onSuccess: (res) => {
      queryClient.setQueryData(['company'], (old: Company | undefined) => ({ ...(old ?? emptyCompany), logo_url: res.logo_url }));
      queryClient.setQueryData(['company-branding'], (old: { name?: string; logo_url?: string | null } | undefined) => ({
        name: old?.name ?? data?.name ?? 'Inventory Management',
        logo_url: res.logo_url,
      }));
      showSuccess('Logo uploaded successfully');
    },
    onError: (error: unknown) => {
      const detail = getApiDetail(error);
      showError(getApiDetailMessage(detail, 'Failed to upload logo'));
    },
  });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) logoMutation.mutate(file);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const onSubmit = (values: CompanyForm): void => {
    const parsed = schema.safeParse(values);
    if (!parsed.success) {
      showError(parsed.error.issues[0]?.message ?? 'Validation failed');
      return;
    }

    const payload: Company = {
      ...(data ?? emptyCompany),
      ...parsed.data,
      legal_name: normalizeOptional(parsed.data.legal_name),
      gstin: normalizeOptional(parsed.data.gstin)?.toUpperCase() ?? null,
      gstin_status: parsed.data.gstin_status ?? 'non-registered',
      pan: normalizeOptional(parsed.data.pan)?.toUpperCase() ?? null,
      company_director_name: normalizeOptional(parsed.data.company_director_name),
      company_director_contact: normalizeOptional(parsed.data.company_director_contact),
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
      account_holder_name: normalizeOptional(parsed.data.account_holder_name),
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
            {/* Logo Section */}
            <div className="hms-card p-6 flex items-center gap-6">
              <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-xl bg-neutral-100 border-2 border-dashed border-neutral-300 overflow-hidden">
                {data?.logo_url ? (
                  <img src={getStaticUrl(data.logo_url) ?? ''} alt="Logo" className="h-full w-full object-contain" />
                ) : (
                  <span className="material-icons text-neutral-400 text-3xl">image</span>
                )}
              </div>
              <div>
                <h2 className="font-display text-lg font-bold text-neutral-900 mb-1">Company Logo</h2>
                <p className="text-sm text-neutral-500 mb-3">Upload your company logo (PNG/JPG, max 2MB). Maps to dashboards and PDFs.</p>
                <input type="file" ref={fileInputRef} className="hidden" accept="image/png, image/jpeg" onChange={handleFileChange} />
                <button type="button" onClick={() => fileInputRef.current?.click()} className="rounded-lg border border-neutral-200 bg-white px-4 py-2 text-sm font-semibold text-neutral-700 hover:bg-neutral-50 disabled:opacity-50" disabled={logoMutation.isPending}>
                  {logoMutation.isPending ? 'Uploading...' : 'Upload Logo'}
                </button>
              </div>
            </div>

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
                  <label htmlFor="company_director_name" className="hms-label">Company Director Name</label>
                  <input id="company_director_name" className="hms-input" placeholder="e.g., John Doe" {...register('company_director_name')} />
                </div>
                <div>
                  <label htmlFor="company_director_contact" className="hms-label">Company Director Contact</label>
                  <input id="company_director_contact" className="hms-input" placeholder="e.g., +91-9876543210" {...register('company_director_contact')} />
                </div>
                <div>
                  <label htmlFor="gstin_status" className="hms-label">GSTIN Registration Status</label>
                  <div className="flex gap-4">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input type="radio" value="registered" {...register('gstin_status')} className="w-4 h-4" />
                      <span className="text-sm">Registered</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input type="radio" value="non-registered" {...register('gstin_status')} className="w-4 h-4" />
                      <span className="text-sm">Non-Registered</span>
                    </label>
                  </div>
                </div>
                <div>
                  <label htmlFor="company_gstin" className="hms-label">{gstin_status === 'registered' ? 'GSTIN *' : 'GSTIN'}</label>
                  {gstin_status === 'registered' ? (
                    <input id="company_gstin" className="hms-input" placeholder="e.g. 33AABCT1234F1Z5" {...register('gstin')} />
                  ) : (
                    <div className="hms-input bg-neutral-100 text-neutral-500 flex items-center">NA</div>
                  )}
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
                  <label htmlFor="account_holder_name" className="hms-label">Account Holder Name</label>
                  <input id="account_holder_name" className="hms-input" {...register('account_holder_name')} />
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
