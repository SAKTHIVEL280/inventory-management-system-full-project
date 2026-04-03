import { type FocusEvent, useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { customersApi } from '../api/customers';
import { companyApi } from '../api/company';
import { Customer } from '../types';
import { AppLayout } from '../components/AppLayout';
import { PageEmpty, PageError, PageLoading } from '../components/PageState';
import { showError, showSuccess, confirmWithToast } from '../utils/toastHelper';
import { getApiDetail, getApiDetailMessage } from '../utils/apiError';

const GSTIN_REGEX = /^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/i;

const STATE_ABBREVIATIONS: Record<string, string> = {
  'andhra pradesh': 'AP',
  'arunachal pradesh': 'AR',
  assam: 'AS',
  bihar: 'BR',
  chhattisgarh: 'CG',
  goa: 'GA',
  gujarat: 'GJ',
  haryana: 'HR',
  'himachal pradesh': 'HP',
  jharkhand: 'JH',
  karnataka: 'KA',
  kerala: 'KL',
  'madhya pradesh': 'MP',
  maharashtra: 'MH',
  manipur: 'MN',
  meghalaya: 'ML',
  mizoram: 'MZ',
  nagaland: 'NL',
  odisha: 'OD',
  punjab: 'PB',
  rajasthan: 'RJ',
  sikkim: 'SK',
  'tamil nadu': 'TN',
  telangana: 'TS',
  tripura: 'TR',
  'uttar pradesh': 'UP',
  uttarakhand: 'UK',
  'west bengal': 'WB',
  delhi: 'DL',
};

const STATE_OPTIONS = Object.entries(STATE_ABBREVIATIONS)
  .map(([state, code]) => ({ state, code }))
  .sort((left, right) => left.state.localeCompare(right.state));

const COUNTRIES = ['India', 'United States', 'United Arab Emirates', 'United Kingdom', 'Singapore', 'Australia'];

const schema = z.object({
  company_name: z.string().min(1, 'Company name required'),
  phone: z.string().regex(/^[6-9]\d{9}$/, 'Must be a valid 10-digit Indian mobile number'),
  customer_type: z.enum(['regular', 'dealer', 'distributor', 'retail']),
  business_type: z.enum(['domestic', 'international']).default('domestic'),
  company_director_name: z.string().optional(),
  company_director_contact: z.string().optional(),
  contact_person: z.string().optional(),
  email: z.string().email('Invalid email format').optional().or(z.literal('')),
  gstin_status: z.enum(['registered', 'non-registered']).default('non-registered'),
  gstin: z.string().optional().or(z.literal('')),
  billing_address_line1: z.string().optional(),
  billing_address_line2: z.string().optional(),
  billing_city: z.string().optional(),
  billing_state: z.string().optional(),
  billing_state_code: z.string().optional(),
  billing_country: z.string().optional(),
  billing_pincode: z.string().optional(),
  same_as_billing: z.boolean().default(true),
  payment_terms_days: z.coerce.number().min(0, 'Cannot be negative').default(30),
  credit_limit: z.coerce.number().min(0, 'Cannot be negative').default(0),
  currency_code: z.string().default('INR'),
}).superRefine((value, ctx) => {
  if (value.gstin_status === 'registered') {
    if (!value.gstin || !value.gstin.trim()) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['gstin'], message: 'GSTIN is required for registered customers' });
      return;
    }
    if (!GSTIN_REGEX.test(value.gstin.trim())) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['gstin'], message: 'Invalid GSTIN format' });
    }
  }
});

type CustomerForm = z.infer<typeof schema>;

const normalizeOptional = (value?: string): string | null => value?.trim() || null;

const buildDefaultValues = (company?: { address_line1?: string | null; address_line2?: string | null; city?: string | null; state?: string | null; state_code?: string | null; pincode?: string | null; }): CustomerForm => ({
  company_name: '',
  phone: '',
  customer_type: 'regular',
  business_type: 'domestic',
  company_director_name: '',
  company_director_contact: '',
  contact_person: '',
  email: '',
  gstin_status: 'non-registered',
  gstin: '',
  billing_address_line1: company?.address_line1 ?? '',
  billing_address_line2: company?.address_line2 ?? '',
  billing_city: company?.city ?? '',
  billing_state: company?.state ?? '',
  billing_state_code: company?.state_code ?? '',
  billing_country: 'India',
  billing_pincode: company?.pincode ?? '',
  same_as_billing: true,
  payment_terms_days: 30,
  credit_limit: 0,
  currency_code: 'INR',
});

const toCustomerCodePreview = (businessType: 'domestic' | 'international', state?: string, stateCode?: string, country?: string): string => {
  const isInternational = businessType === 'international' || !!(country && country.trim().toLowerCase() !== 'india');
  if (isInternational) {
    return 'CUST-INT-XXXXX';
  }

  const normalizedState = (state || '').trim().toLowerCase();
  const codeFromState = STATE_ABBREVIATIONS[normalizedState];
  const codeFromInput = (stateCode || '').trim().replace(/[^a-zA-Z]/g, '').toUpperCase();
  const finalCode = codeFromState || (codeFromInput.length >= 2 ? codeFromInput.slice(0, 2) : 'NA');
  return `CUST-${finalCode}-XXXXX`;
};

const clearZeroOnFocus = (event: FocusEvent<HTMLInputElement>) => {
  if (event.currentTarget.value === '0') {
    event.currentTarget.value = '';
  }
};

const CustomersPage = () => {
  const queryClient = useQueryClient();
  const [editingItem, setEditingItem] = useState<Customer | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [defaultsApplied, setDefaultsApplied] = useState(false);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['customers'],
    queryFn: customersApi.list,
  });

  const { data: companyData } = useQuery({
    queryKey: ['company'],
    queryFn: companyApi.get,
  });

  const { register, handleSubmit, reset, setValue, watch } = useForm<CustomerForm>({
    defaultValues: buildDefaultValues(),
  });

  useEffect(() => {
    if (!editingItem && companyData && !defaultsApplied) {
      reset(buildDefaultValues(companyData));
      setDefaultsApplied(true);
    }
  }, [companyData, defaultsApplied, editingItem, reset]);

  const createMutation = useMutation({
    mutationFn: customersApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customers'] });
      resetForm();
      showSuccess('Customer created successfully');
    },
    onError: (error: unknown) => {
      const detail = getApiDetail(error);
      const errorMessage = getApiDetailMessage(detail, 'Failed to create customer');
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
      const detail = getApiDetail(error);
      const errorMessage = getApiDetailMessage(detail, 'Failed to update customer');
      showError(errorMessage);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => customersApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customers'] });
      showSuccess('Customer deleted successfully');
    },
    onError: (error: unknown) => {
      const detail = getApiDetail(error);
      let errorMessage = 'Failed to delete customer';

      if (typeof detail === 'string') {
        errorMessage = detail;
      } else if (detail && typeof detail === 'object' && !Array.isArray(detail) && detail.error_code === 'OUTSTANDING_EXISTS') {
        errorMessage = 'Cannot delete customer: outstanding balance exists. Please clear dues before deleting.';
      } else if (detail && typeof detail === 'object' && !Array.isArray(detail) && typeof detail.message === 'string') {
        errorMessage = detail.message;
      } else if (Array.isArray(detail)) {
        errorMessage = detail
          .map((d) => d.msg || d.message)
          .filter((m): m is string => Boolean(m && m.trim()))
          .join(', ');
      }

      showError(errorMessage);
    },
  });

  const resetForm = () => {
    setEditingItem(null);
    reset(buildDefaultValues(companyData));
    setDefaultsApplied(true);
    setIsFormOpen(false);
  };

  const startEdit = (item: Customer) => {
    setEditingItem(item);
    setIsFormOpen(true);
    setValue('company_name', item.company_name);
    setValue('phone', item.phone);
    setValue('customer_type', item.customer_type);
    setValue('business_type', item.business_type ?? 'domestic');
    setValue('company_director_name', item.company_director_name ?? '');
    setValue('company_director_contact', item.company_director_contact ?? '');
    setValue('contact_person', item.contact_person ?? '');
    setValue('email', item.email ?? '');
    setValue('gstin_status', item.gstin_status ?? 'non-registered');
    setValue('gstin', item.gstin ?? '');
    setValue('billing_address_line1', item.billing_address_line1 ?? '');
    setValue('billing_address_line2', item.billing_address_line2 ?? '');
    setValue('billing_city', item.billing_city ?? '');
    setValue('billing_state', item.billing_state ?? '');
    setValue('billing_state_code', item.billing_state_code ?? '');
    setValue('billing_country', item.billing_country ?? 'India');
    setValue('billing_pincode', item.billing_pincode ?? '');
    setValue('same_as_billing', item.same_as_billing ?? true);
    setValue('payment_terms_days', item.payment_terms_days ?? 30);
    setValue('credit_limit', item.credit_limit ?? 0);
    setValue('currency_code', item.currency_code ?? 'INR');
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
      company_director_name: normalizeOptional(parsed.data.company_director_name),
      company_director_contact: normalizeOptional(parsed.data.company_director_contact),
      contact_person: normalizeOptional(parsed.data.contact_person),
      email: normalizeOptional(parsed.data.email),
      phone: parsed.data.phone.trim(),
      alternate_phone: null,
      gstin_status: parsed.data.gstin_status,
      gstin: parsed.data.gstin_status === 'registered' ? (normalizeOptional(parsed.data.gstin)?.toUpperCase() ?? null) : null,
      pan: null,
      customer_type: parsed.data.customer_type,
      business_type: parsed.data.business_type,
      billing_address_line1: normalizeOptional(parsed.data.billing_address_line1),
      billing_address_line2: normalizeOptional(parsed.data.billing_address_line2),
      billing_city: normalizeOptional(parsed.data.billing_city),
      billing_state: normalizeOptional(parsed.data.billing_state),
      billing_state_code: normalizeOptional(parsed.data.billing_state_code),
      billing_country: normalizeOptional(parsed.data.billing_country),
      billing_pincode: normalizeOptional(parsed.data.billing_pincode),
      shipping_address_line1: null,
      shipping_address_line2: null,
      shipping_city: null,
      shipping_state: null,
      shipping_state_code: null,
      shipping_country: null,
      shipping_pincode: null,
      same_as_billing: parsed.data.same_as_billing ?? true,
      credit_limit: parsed.data.credit_limit,
      payment_terms_days: parsed.data.payment_terms_days,
      currency_code: parsed.data.currency_code,
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
  const businessType = watch('business_type');
  const gstinStatus = watch('gstin_status');
  const billingState = watch('billing_state');
  const billingStateCode = watch('billing_state_code');
  const billingCountry = watch('billing_country');
  const customerCodePreview = toCustomerCodePreview(businessType, billingState, billingStateCode, billingCountry);

  return (
    <AppLayout title="Customer Master">
      <div className="space-y-6">
        <div className="hms-card overflow-hidden">
          <div className="border-b border-neutral-200 px-5 py-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="font-display text-lg font-bold text-neutral-900">
                  {editingItem ? 'Modify/Change Customer' : 'New Customer'}
                </h2>
                <p className="text-xs text-neutral-500">Create or modify customer master records in a collapsible form.</p>
              </div>
              <div className="flex items-center gap-2">
                {!isFormOpen && (
                  <button
                    type="button"
                    onClick={() => {
                      setEditingItem(null);
                      reset(buildDefaultValues(companyData));
                      setDefaultsApplied(true);
                      setIsFormOpen(true);
                    }}
                    className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white transition hover:bg-primary/90"
                  >
                    + New Customer
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
            <div className="p-5">
              {editingItem && (
                <div className="mb-4 flex items-center justify-between border-b border-neutral-200 pb-4">
                  <h3 className="text-sm font-semibold text-neutral-900">Modifying/Changing: {editingItem.company_name}</h3>
                  <button type="button" onClick={resetForm} className="text-sm text-neutral-500 hover:text-neutral-700">
                    Cancel
                  </button>
                </div>
              )}
              <form className="space-y-3" onSubmit={handleSubmit(onSubmit)}>
                <div>
                  <label htmlFor="company_name" className="hms-label">Company name</label>
                  <input id="company_name" className="hms-input" placeholder="Company name" {...register('company_name')} />
                </div>
                <div>
                  <label htmlFor="business_type" className="hms-label">Business Type</label>
                  <select id="business_type" className="hms-input" {...register('business_type')}>
                    <option value="domestic">Domestic</option>
                    <option value="international">International</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="customer_code_preview" className="hms-label">Customer ID (Auto)</label>
                  <input id="customer_code_preview" className="hms-input bg-neutral-100" value={customerCodePreview} readOnly />
                  <p className="mt-1 text-xs text-neutral-500">Prefix auto-fills from selected State/Country; running number is assigned on save.</p>
                </div>
                <div>
                  <label htmlFor="company_director_name" className="hms-label">Company Director Name</label>
                  <input id="company_director_name" className="hms-input" placeholder="e.g. John Doe" {...register('company_director_name')} />
                </div>
                <div>
                  <label htmlFor="company_director_contact" className="hms-label">Company Director Contact</label>
                  <input id="company_director_contact" className="hms-input" placeholder="e.g. +91-9876543210" {...register('company_director_contact')} />
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
                  <label htmlFor="gstin_status" className="hms-label">GSTIN Status</label>
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
                  <label htmlFor="gstin" className="hms-label">{gstinStatus === 'registered' ? 'GSTIN *' : 'GSTIN'}</label>
                  {gstinStatus === 'registered' ? (
                    <input id="gstin" className="hms-input" placeholder="GSTIN" {...register('gstin')} />
                  ) : (
                    <div className="hms-input bg-neutral-100 text-neutral-500 flex items-center">NA</div>
                  )}
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

                <div className="grid grid-cols-3 gap-2">
                    <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Payment Terms (Days)</label><input type="number" min="0" className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" {...register('payment_terms_days')} onFocus={clearZeroOnFocus} /></div>
                    <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Credit Limit</label><input type="number" min="0" className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" {...register('credit_limit')} onFocus={clearZeroOnFocus} /></div>
                    <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Currency</label><select className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" {...register('currency_code')}><option value="INR">INR (₹)</option><option value="USD">USD ($)</option><option value="EUR">EUR (€)</option><option value="GBP">GBP (£)</option></select></div>
                </div>

                {/* BUG-30: Address fields */}
                <div className="pt-2 border-t border-neutral-100">
                  <p className="text-xs font-bold uppercase tracking-wider text-neutral-500 mb-2">Billing Address</p>
                </div>
                <div>
                  <label htmlFor="billing_address_line1" className="hms-label">Address</label>
                  <input id="billing_address_line1" className="hms-input" placeholder="Address line 1" {...register('billing_address_line1')} />
                </div>
                <div>
                  <label htmlFor="billing_address_line2" className="hms-label">Address line 2</label>
                  <input id="billing_address_line2" className="hms-input" placeholder="Address line 2" {...register('billing_address_line2')} />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label htmlFor="billing_city" className="hms-label">City</label>
                    <input id="billing_city" className="hms-input" placeholder="City" {...register('billing_city')} />
                  </div>
                  <div>
                    <label htmlFor="billing_state" className="hms-label">State</label>
                    <select id="billing_state" className="hms-input" {...register('billing_state')}>
                      <option value="">Select state</option>
                      {STATE_OPTIONS.map(({ state, code }) => (
                        <option key={state} value={state}>
                          {state.replace(/\b\w/g, (char) => char.toUpperCase())} ({code})
                        </option>
                      ))}
                    </select>
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
                <div>
                  <label htmlFor="billing_country" className="hms-label">Country</label>
                  <select id="billing_country" className="hms-input" {...register('billing_country')}>
                    {COUNTRIES.map((country) => (
                      <option key={country} value={country}>{country}</option>
                    ))}
                  </select>
                </div>
                <div className="flex items-center gap-2">
                  <input id="same_as_billing" type="checkbox" className="rounded border-neutral-300" {...register('same_as_billing')} />
                  <label htmlFor="same_as_billing" className="text-sm text-neutral-600">Shipping same as billing</label>
                </div>
                <div className="flex justify-end gap-3 mt-6">
                <button type="submit" disabled={isSaving} className="w-full rounded-lg bg-primary px-5 py-2.5 text-sm font-bold text-white shadow-lg shadow-primary/20 transition hover:bg-primary/90 disabled:opacity-60">
                  {isSaving ? 'Saving...' : editingItem ? 'Update Customer' : 'Create Customer'}
                </button>
                </div>
              </form>
            </div>
          )}
        </div>

        <div className="hms-card overflow-hidden">
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
                          Modify/Change
                        </button>
                        <button 
                          type="button" 
                          onClick={() => {
                            const customerName = item.company_name;
                            confirmWithToast(
                              `Are you sure you want to delete "${customerName}"? This action cannot be undone.`,
                              {
                                onConfirm: () => deleteMutation.mutate(item.id),
                                type: 'danger',
                              }
                            );
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
