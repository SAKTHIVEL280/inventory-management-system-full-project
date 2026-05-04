import { useEffect, useRef } from 'react';
import { useForm } from 'react-hook-form';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { z } from 'zod';
import { companyApi } from '../api/company';
import { authApi } from '../api/auth';
import { Company } from '../types';
import { AppLayout } from '../components/AppLayout';
import { PageError, PageLoading } from '../components/PageState';
import { getStaticUrl } from '../utils/url_utils';
import { getApiDetail, getApiDetailMessage } from '../utils/apiError';
import { showError, showSuccess } from '../utils/toastHelper';
import { useAuthStore } from '../store/auth';

const schema = z.object({
  name: z.string().min(1, 'Company name is required'),
  legal_name: z.string().optional(),
  gstin: z.string().optional(),
  gstin_status: z.string().optional(),
  pan: z.string().optional(),
  import_export_number: z.string().optional(),
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
  country: z.string().optional(),
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

const GST_STATE_CODE_ENTRIES: Array<[string, string, string]> = [
  ['01', 'JK', 'Jammu and Kashmir'],
  ['02', 'HP', 'Himachal Pradesh'],
  ['03', 'PB', 'Punjab'],
  ['04', 'CH', 'Chandigarh'],
  ['05', 'UK', 'Uttarakhand'],
  ['06', 'HR', 'Haryana'],
  ['07', 'DL', 'Delhi'],
  ['08', 'RJ', 'Rajasthan'],
  ['09', 'UP', 'Uttar Pradesh'],
  ['10', 'BR', 'Bihar'],
  ['11', 'SK', 'Sikkim'],
  ['12', 'AR', 'Arunachal Pradesh'],
  ['13', 'NL', 'Nagaland'],
  ['14', 'MN', 'Manipur'],
  ['15', 'MZ', 'Mizoram'],
  ['16', 'TR', 'Tripura'],
  ['17', 'ML', 'Meghalaya'],
  ['18', 'AS', 'Assam'],
  ['19', 'WB', 'West Bengal'],
  ['20', 'JH', 'Jharkhand'],
  ['21', 'OR', 'Odisha'],
  ['22', 'CT', 'Chhattisgarh'],
  ['23', 'MP', 'Madhya Pradesh'],
  ['24', 'GJ', 'Gujarat'],
  ['26', 'DD', 'Dadra and Nagar Haveli and Daman and Diu'],
  ['27', 'MH', 'Maharashtra'],
  ['28', 'AP', 'Andhra Pradesh'],
  ['29', 'KA', 'Karnataka'],
  ['30', 'GA', 'Goa'],
  ['31', 'LD', 'Lakshadweep'],
  ['32', 'KL', 'Kerala'],
  ['33', 'TN', 'Tamil Nadu'],
  ['34', 'PY', 'Puducherry'],
  ['35', 'AN', 'Andaman and Nicobar Islands'],
  ['36', 'TS', 'Telangana'],
  ['37', 'LA', 'Ladakh'],
  ['38', 'LA', 'Ladakh'],
];

const STATE_CODE_MAP = GST_STATE_CODE_ENTRIES.reduce<Record<string, string>>((acc, [numericCode, abbreviation, stateName]) => {
  acc[numericCode] = numericCode;
  acc[abbreviation.toUpperCase()] = numericCode;
  acc[stateName.toLowerCase()] = numericCode;
  return acc;
}, {});

const STATE_NAME_BY_CODE = GST_STATE_CODE_ENTRIES.reduce<Record<string, string>>((acc, [numericCode, _abbreviation, stateName]) => {
  acc[numericCode] = stateName;
  return acc;
}, {});

const canonicalStateCode = (value?: string | null): string | null => {
  const raw = (value || '').trim();
  if (!raw) return null;

  const stateToken = raw.toLowerCase();
  if (STATE_CODE_MAP[stateToken]) return STATE_CODE_MAP[stateToken];

  const upperToken = raw.toUpperCase();
  if (/^\d+$/.test(upperToken)) {
    const padded = upperToken.padStart(2, '0');
    return STATE_CODE_MAP[padded] || padded;
  }

  return STATE_CODE_MAP[upperToken] || null;
};

const stateNameFromStateCode = (value?: string | null): string | null => {
  const code = canonicalStateCode(value);
  if (!code) return null;
  return STATE_NAME_BY_CODE[code] || null;
};

const stateMismatchMessage = (stateValue?: string | null, stateCodeValue?: string | null): string | null => {
  const codeFromState = canonicalStateCode(stateValue);
  const codeFromInput = canonicalStateCode(stateCodeValue);
  if (codeFromState && codeFromInput && codeFromState !== codeFromInput) {
    return 'State does not match the given state code';
  }
  return null;
};

const PLACEHOLDER_COMPANY_NAMES = new Set(['your company name', 'my company']);

const normalizeCompanyNameForForm = (value?: string | null): string => {
  const trimmed = (value || '').trim();
  if (!trimmed) return '';
  if (PLACEHOLDER_COMPANY_NAMES.has(trimmed.toLowerCase())) return '';
  return trimmed;
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

const mapCompanyToFormValues = (company?: Company): CompanyForm => ({
  name: normalizeCompanyNameForForm(company?.name),
  legal_name: company?.legal_name ?? '',
  gstin: company?.gstin ?? '',
  gstin_status: company?.gstin_status ?? 'non-registered',
  pan: company?.pan ?? '',
  import_export_number: company?.import_export_number ?? '',
  company_director_name: company?.company_director_name ?? '',
  company_director_contact: company?.company_director_contact ?? '',
  state_code: company?.state_code ?? '',
  phone: company?.phone ?? '',
  email: company?.email ?? '',
  website: company?.website ?? '',
  address_line1: company?.address_line1 ?? '',
  address_line2: company?.address_line2 ?? '',
  city: company?.city ?? '',
  state: company?.state ?? '',
  country: company?.country ?? '',
  pincode: company?.pincode ?? '',
  bank_name: company?.bank_name ?? '',
  account_holder_name: company?.account_holder_name ?? '',
  bank_account_no: company?.bank_account_no ?? '',
  bank_ifsc: company?.bank_ifsc ?? '',
  bank_branch: company?.bank_branch ?? '',
});

const CompanyPage = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const setUser = useAuthStore((state) => state.setUser);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const ambassadorFileInputRef = useRef<HTMLInputElement>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['company'],
    queryFn: companyApi.get,
  });

  const { register, handleSubmit, reset, setValue, watch, formState: { isDirty } } = useForm<CompanyForm>({
    defaultValues: mapCompanyToFormValues(),
  });

  useEffect(() => {
    if (!data || isDirty) return;
    reset(mapCompanyToFormValues(data));
  }, [data, isDirty, reset]);

  const gstin_status = watch('gstin_status');
  const stateValue = watch('state') ?? '';
  const stateCodeValue = watch('state_code') ?? '';

  useEffect(() => {
    const resolvedFromCode = stateNameFromStateCode(stateCodeValue);
    if (resolvedFromCode && stateValue.trim().length === 0) {
      setValue('state', resolvedFromCode, { shouldDirty: false });
    }

    if (!stateCodeValue) {
      const resolvedFromState = canonicalStateCode(stateValue);
      if (resolvedFromState && resolvedFromState !== stateCodeValue) {
        setValue('state_code', resolvedFromState, { shouldDirty: false });
      }
    }
  }, [setValue, stateCodeValue, stateValue]);

  const mutation = useMutation({
    mutationFn: (payload: Company) => companyApi.update(payload),
    onSuccess: async (updated) => {
      queryClient.setQueryData(['company'], updated);
      queryClient.setQueryData(['company-branding'], (old: { name?: string; logo_url?: string | null } | undefined) => ({
        name: updated.name,
        logo_url: updated.logo_url ?? old?.logo_url ?? null,
      }));
      reset(mapCompanyToFormValues(updated));
      showSuccess('Company profile saved successfully');
      try {
        const me = await authApi.getMe();
        setUser(me);
      } catch {
        // Ignore user refresh errors; next login will refresh context.
      }
      navigate('/dashboard');
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

  const ambassadorLogoMutation = useMutation({
    mutationFn: companyApi.uploadAmbassadorLogo,
    onSuccess: (res) => {
      queryClient.setQueryData(['company'], (old: Company | undefined) => ({
        ...(old ?? emptyCompany),
        ambassador_logo_url: res.ambassador_logo_url,
      }));
      showSuccess('Ambassador logo uploaded successfully');
    },
    onError: (error: unknown) => {
      const detail = getApiDetail(error);
      showError(getApiDetailMessage(detail, 'Failed to upload ambassador logo'));
    },
  });

  const removeAmbassadorLogoMutation = useMutation({
    mutationFn: companyApi.removeAmbassadorLogo,
    onSuccess: () => {
      queryClient.setQueryData(['company'], (old: Company | undefined) => ({
        ...(old ?? emptyCompany),
        ambassador_logo_url: null,
      }));
      showSuccess('Ambassador logo removed successfully');
    },
    onError: (error: unknown) => {
      const detail = getApiDetail(error);
      showError(getApiDetailMessage(detail, 'Failed to remove ambassador logo'));
    },
  });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) logoMutation.mutate(file);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleAmbassadorFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) ambassadorLogoMutation.mutate(file);
    if (ambassadorFileInputRef.current) ambassadorFileInputRef.current.value = '';
  };

  const handleRemoveAmbassadorLogo = () => {
    removeAmbassadorLogoMutation.mutate();
  };

  const onSubmit = (values: CompanyForm): void => {
    const parsed = schema.safeParse(values);
    if (!parsed.success) {
      showError(parsed.error.issues[0]?.message ?? 'Validation failed');
      return;
    }

    const stateMismatch = stateMismatchMessage(parsed.data.state, parsed.data.state_code);
    if (stateMismatch) {
      showError(stateMismatch);
      return;
    }

    const stateResolved = normalizeOptional(parsed.data.state) || stateNameFromStateCode(parsed.data.state_code);
    const stateCodeResolved = canonicalStateCode(parsed.data.state_code) || canonicalStateCode(stateResolved);

    const payload: Company = {
      ...(data ?? emptyCompany),
      ...parsed.data,
      legal_name: normalizeOptional(parsed.data.legal_name),
      gstin: normalizeOptional(parsed.data.gstin)?.toUpperCase() ?? null,
      gstin_status: parsed.data.gstin_status ?? 'non-registered',
      pan: normalizeOptional(parsed.data.pan)?.toUpperCase() ?? null,
      import_export_number: normalizeOptional(parsed.data.import_export_number),
      company_director_name: normalizeOptional(parsed.data.company_director_name),
      company_director_contact: normalizeOptional(parsed.data.company_director_contact),
      state_code: stateCodeResolved,
      phone: normalizeOptional(parsed.data.phone),
      email: normalizeOptional(parsed.data.email),
      website: normalizeOptional(parsed.data.website),
      address_line1: normalizeOptional(parsed.data.address_line1),
      address_line2: normalizeOptional(parsed.data.address_line2),
      city: normalizeOptional(parsed.data.city),
      state: stateResolved,
      country: normalizeOptional(parsed.data.country),
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

            <div className="hms-card p-6 flex items-center gap-6">
              <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-xl bg-neutral-100 border-2 border-dashed border-neutral-300 overflow-hidden">
                {data?.ambassador_logo_url ? (
                  <img src={getStaticUrl(data.ambassador_logo_url) ?? ''} alt="Ambassador Logo" className="h-full w-full object-contain" />
                ) : (
                  <span className="material-icons text-neutral-400 text-3xl">image</span>
                )}
              </div>
              <div>
                <h2 className="font-display text-lg font-bold text-neutral-900 mb-1">Company Ambassador Logo</h2>
                <p className="text-sm text-neutral-500 mb-3">Used as a subtle center watermark in Purchase Order, Sales Invoice, and Quotation PDFs (PNG/JPG, max 2MB).</p>
                <input
                  type="file"
                  ref={ambassadorFileInputRef}
                  className="hidden"
                  accept="image/png, image/jpeg"
                  onChange={handleAmbassadorFileChange}
                />
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => ambassadorFileInputRef.current?.click()}
                    className="rounded-lg border border-neutral-200 bg-white px-4 py-2 text-sm font-semibold text-neutral-700 hover:bg-neutral-50 disabled:opacity-50"
                    disabled={ambassadorLogoMutation.isPending || removeAmbassadorLogoMutation.isPending}
                  >
                    {ambassadorLogoMutation.isPending
                      ? 'Uploading...'
                      : (data?.ambassador_logo_url ? 'Replace Ambassador Logo' : 'Upload Ambassador Logo')}
                  </button>
                  {data?.ambassador_logo_url && (
                    <button
                      type="button"
                      onClick={handleRemoveAmbassadorLogo}
                      className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm font-semibold text-red-700 hover:bg-red-100 disabled:opacity-50"
                      disabled={removeAmbassadorLogoMutation.isPending || ambassadorLogoMutation.isPending}
                    >
                      {removeAmbassadorLogoMutation.isPending ? 'Removing...' : 'Remove Ambassador Logo'}
                    </button>
                  )}
                </div>
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
                  <label htmlFor="import_export_number" className="hms-label">Import &amp; Export Number</label>
                  <input id="import_export_number" className="hms-input" placeholder="e.g. 0310001234" {...register('import_export_number')} />
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
                  <label htmlFor="country" className="hms-label">Country</label>
                  <input id="country" className="hms-input" {...register('country')} />
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
