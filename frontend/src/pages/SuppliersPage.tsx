import { useEffect, useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { suppliersApi } from '../api/suppliers';
import { Supplier } from '../types';
import { AppLayout } from '../components/AppLayout';
import { PageEmpty, PageError, PageLoading } from '../components/PageState';
import { getApiDetail, getApiDetailMessage } from '../utils/apiError';
import { showError, showSuccess } from '../utils/toastHelper';

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
  company_director_name: z.string().optional(),
  company_director_contact: z.string().optional(),
  contact_person: z.string().optional(),
  email: z.string().email('Invalid email format').optional().or(z.literal('')),
  gstin_status: z.enum(['registered', 'non-registered']).default('non-registered'),
  gstin: z.string().optional().or(z.literal('')),
  business_type: z.enum(['domestic', 'international']).default('domestic'),
  address_line1: z.string().optional(),
  address_line2: z.string().optional(),
  city: z.string().optional(),
  state: z.string().optional(),
  state_code: z.string().optional(),
  billing_country: z.string().optional(),
  pincode: z.string().optional(),
  place_of_supply: z.string().optional(),
  payment_terms_days: z.coerce.number().min(0).default(30),
}).superRefine((value, ctx) => {
  if (value.gstin_status === 'registered') {
    if (!value.gstin || !value.gstin.trim()) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['gstin'], message: 'GSTIN is required for registered suppliers' });
      return;
    }
    if (!GSTIN_REGEX.test(value.gstin.trim())) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['gstin'], message: 'Invalid GSTIN format' });
    }
  }
});

type SupplierForm = z.infer<typeof schema>;
type SupplierSortField = 'created_at' | 'company_name' | 'supplier_code' | 'phone' | 'gstin_status';

const formatDisplayDate = (value?: string | null): string => {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '—';
  return parsed.toLocaleDateString();
};

const normalizeOptional = (value?: string): string | null => value?.trim() || null;

const toSupplierCodePreview = (businessType: 'domestic' | 'international', state?: string, stateCode?: string, country?: string): string => {
  const isInternational = businessType === 'international' || !!(country && country.trim().toLowerCase() !== 'india');
  if (isInternational) {
    return 'SUPP-INT-XXXXX';
  }

  const normalizedState = (state || '').trim().toLowerCase();
  const codeFromState = STATE_ABBREVIATIONS[normalizedState];
  const codeFromInput = (stateCode || '').trim().replace(/[^a-zA-Z]/g, '').toUpperCase();
  const finalCode = codeFromState || (codeFromInput.length >= 2 ? codeFromInput.slice(0, 2) : 'NA');
  return `SUPP-${finalCode}-XXXXX`;
};

const SuppliersPage = () => {
  const queryClient = useQueryClient();
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<Supplier | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState<SupplierSortField>('created_at');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');
  const [gstinFilter, setGstinFilter] = useState<'all' | 'registered' | 'non-registered'>('all');
  const [businessTypeFilter, setBusinessTypeFilter] = useState<'all' | 'domestic' | 'international'>('all');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [createdFrom, setCreatedFrom] = useState('');
  const [createdTo, setCreatedTo] = useState('');

  const { data, isLoading, isError } = useQuery({
    queryKey: ['suppliers'],
    queryFn: () => suppliersApi.list({ page: 1, page_size: 500 }),
  });

  const { register, handleSubmit, reset, setValue, watch } = useForm<SupplierForm>({
    defaultValues: {
      company_name: '',
      company_director_name: '',
      company_director_contact: '',
      phone: '',
      contact_person: '',
      email: '',
      gstin_status: 'non-registered',
      gstin: '',
      business_type: 'domestic',
      address_line1: '',
      address_line2: '',
      city: '',
      state: '',
      state_code: '',
      billing_country: 'India',
      pincode: '',
      place_of_supply: '',
      payment_terms_days: 30,
    },
  });

  const createMutation = useMutation({
    mutationFn: suppliersApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['suppliers'] });
      showSuccess('Supplier created successfully');
      resetForm();
    },
    onError: (error: unknown) => {
      const detail = getApiDetail(error);
      showError(getApiDetailMessage(detail, 'Failed to create supplier'));
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<Supplier> }) => suppliersApi.update(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['suppliers'] });
      showSuccess('Supplier updated successfully');
      resetForm();
    },
    onError: (error: unknown) => {
      const detail = getApiDetail(error);
      showError(getApiDetailMessage(detail, 'Failed to update supplier'));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => suppliersApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['suppliers'] });
      setDeleteConfirm(null);
      showSuccess('Supplier deleted successfully');
    },
    onError: (error: unknown) => {
      const detail = getApiDetail(error);
      let message = 'Failed to delete supplier';

      if (typeof detail === 'string') {
        message = detail;
      } else if (detail && typeof detail === 'object' && !Array.isArray(detail) && typeof detail.message === 'string') {
        message = detail.message;
      } else if (detail && typeof detail === 'object' && !Array.isArray(detail) && detail.error_code === 'OUTSTANDING_EXISTS') {
        message = 'Cannot delete supplier: There are outstanding payments. Please clear all dues before deleting.';
      } else if (Array.isArray(detail)) {
        message =
          detail
            .map((d) => d.msg || d.message)
            .filter((m): m is string => Boolean(m && m.trim()))
            .join(', ') || message;
      }

      showError(message);
      setDeleteConfirm(null);
    },
  });

  const resetForm = () => {
    setEditingItem(null);
    setIsFormOpen(false);
    reset({
      company_name: '',
      company_director_name: '',
      company_director_contact: '',
      phone: '',
      contact_person: '',
      email: '',
      gstin_status: 'non-registered',
      gstin: '',
      business_type: 'domestic',
      address_line1: '',
      address_line2: '',
      city: '',
      state: '',
      state_code: '',
      billing_country: 'India',
      pincode: '',
      place_of_supply: '',
      payment_terms_days: 30,
    });
  };

  const startEdit = (item: Supplier) => {
    setEditingItem(item);
    setIsFormOpen(true);
    setValue('company_name', item.company_name);
    setValue('company_director_name', item.company_director_name ?? '');
    setValue('company_director_contact', item.company_director_contact ?? '');
    setValue('phone', item.phone);
    setValue('contact_person', item.contact_person ?? '');
    setValue('email', item.email ?? '');
    setValue('gstin_status', item.gstin_status ?? 'non-registered');
    setValue('gstin', item.gstin ?? '');
    setValue('business_type', item.business_type ?? 'domestic');
    setValue('address_line1', item.address_line1 ?? '');
    setValue('address_line2', item.address_line2 ?? '');
    setValue('city', item.city ?? '');
    setValue('state', item.state ?? '');
    setValue('state_code', item.state_code ?? '');
    setValue('billing_country', item.billing_country ?? 'India');
    setValue('pincode', item.pincode ?? '');
    setValue('place_of_supply', item.place_of_supply ?? '');
    setValue('payment_terms_days', item.payment_terms_days ?? 30);
  };

  const onSubmit = (values: SupplierForm): void => {
    const parsed = schema.safeParse(values);
    if (!parsed.success) {
      showError(parsed.error.issues[0]?.message ?? 'Validation failed');
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
      business_type: parsed.data.business_type,
      address_line1: normalizeOptional(parsed.data.address_line1),
      address_line2: normalizeOptional(parsed.data.address_line2),
      city: normalizeOptional(parsed.data.city),
      state: normalizeOptional(parsed.data.state),
      state_code: normalizeOptional(parsed.data.state_code),
      billing_country: normalizeOptional(parsed.data.billing_country),
      pincode: normalizeOptional(parsed.data.pincode),
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
  const filteredItems = useMemo(() => {
    const normalizedSearch = searchTerm.trim().toLowerCase();
    const fromTime = createdFrom ? new Date(`${createdFrom}T00:00:00`).getTime() : null;
    const toTime = createdTo ? new Date(`${createdTo}T23:59:59.999`).getTime() : null;

    const filtered = items.filter((item) => {
      if (normalizedSearch) {
        const haystack = [
          item.supplier_code ?? '',
          item.company_name ?? '',
          item.phone ?? '',
          item.contact_person ?? '',
          item.email ?? '',
        ]
          .join(' ')
          .toLowerCase();

        if (!haystack.includes(normalizedSearch)) {
          return false;
        }
      }

      if (gstinFilter !== 'all' && (item.gstin_status ?? 'non-registered') !== gstinFilter) {
        return false;
      }

      if (businessTypeFilter !== 'all' && (item.business_type ?? 'domestic') !== businessTypeFilter) {
        return false;
      }

      if (statusFilter !== 'all') {
        const expectedActive = statusFilter === 'active';
        if ((item.is_active ?? true) !== expectedActive) {
          return false;
        }
      }

      if (fromTime !== null || toTime !== null) {
        const createdTime = item.created_at ? new Date(item.created_at).getTime() : NaN;
        if (!Number.isFinite(createdTime)) {
          return false;
        }
        if (fromTime !== null && createdTime < fromTime) {
          return false;
        }
        if (toTime !== null && createdTime > toTime) {
          return false;
        }
      }

      return true;
    });

    filtered.sort((left, right) => {
      let compareResult = 0;

      if (sortBy === 'created_at') {
        const leftValue = left.created_at ? new Date(left.created_at).getTime() : 0;
        const rightValue = right.created_at ? new Date(right.created_at).getTime() : 0;
        compareResult = leftValue - rightValue;
      } else {
        const leftValue = (left[sortBy] ?? '').toString().toLowerCase();
        const rightValue = (right[sortBy] ?? '').toString().toLowerCase();
        compareResult = leftValue.localeCompare(rightValue);
      }

      return sortDirection === 'asc' ? compareResult : -compareResult;
    });

    return filtered;
  }, [
    businessTypeFilter,
    createdFrom,
    createdTo,
    gstinFilter,
    items,
    searchTerm,
    sortBy,
    sortDirection,
    statusFilter,
  ]);
  const isSaving = createMutation.isPending || updateMutation.isPending;
  const isDeleting = deleteMutation.isPending;
  const businessType = watch('business_type');
  const gstinStatus = watch('gstin_status');
  const state = watch('state');
  const stateCode = watch('state_code');
  const country = watch('billing_country');
  const isIndiaCountry = (country || '').trim().toLowerCase() === 'india';
  const supplierCodePreview = toSupplierCodePreview(businessType, state, stateCode, country);
  const supplierCodeDisplay = editingItem?.supplier_code || supplierCodePreview;

  const clearListFilters = () => {
    setSearchTerm('');
    setSortBy('created_at');
    setSortDirection('desc');
    setGstinFilter('all');
    setBusinessTypeFilter('all');
    setStatusFilter('all');
    setCreatedFrom('');
    setCreatedTo('');
  };

  useEffect(() => {
    if (!isIndiaCountry) {
      return;
    }

    const normalizedState = (state || '').trim().toLowerCase();
    const derivedStateCode = STATE_ABBREVIATIONS[normalizedState] ?? '';
    setValue('state_code', derivedStateCode);
  }, [isIndiaCountry, state, setValue]);

  return (
    <AppLayout title="Supplier Master">
      <div className="space-y-6">
        <div className="hms-card overflow-hidden">
          <div className="border-b border-neutral-200 px-5 py-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="font-display text-lg font-bold text-neutral-900">
                  {editingItem ? 'Modify/Change Supplier' : 'New Supplier'}
                </h2>
                <p className="text-xs text-neutral-500">Create or modify supplier master records in a collapsible form.</p>
              </div>
              <div className="flex items-center gap-2">
                {!isFormOpen && (
                  <button
                    type="button"
                    onClick={() => {
                      setEditingItem(null);
                      reset({
                        company_name: '',
                        company_director_name: '',
                        company_director_contact: '',
                        phone: '',
                        contact_person: '',
                        email: '',
                        gstin_status: 'non-registered',
                        gstin: '',
                        business_type: 'domestic',
                        address_line1: '',
                        address_line2: '',
                        city: '',
                        state: '',
                        state_code: '',
                        billing_country: 'India',
                        pincode: '',
                        place_of_supply: '',
                        payment_terms_days: 30,
                      });
                      setIsFormOpen(true);
                    }}
                    className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white transition hover:bg-primary/90"
                  >
                    + New Supplier
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
                  <button type="button" onClick={resetForm} className="text-sm text-neutral-500 hover:text-neutral-700">Cancel</button>
                </div>
              )}
              <form className="space-y-3" onSubmit={handleSubmit(onSubmit)}>
                <div>
                  <label htmlFor="supplier_company_name" className="hms-label">Company name</label>
                  <input id="supplier_company_name" className="hms-input" placeholder="Company name" {...register('company_name')} />
                </div>
                <div>
                  <label htmlFor="supplier_business_type" className="hms-label">Business Type</label>
                  <select id="supplier_business_type" className="hms-input" {...register('business_type')}>
                    <option value="domestic">Domestic</option>
                    <option value="international">International</option>
                  </select>
                </div>
                {editingItem && (
                  <>
                    <div>
                      <label htmlFor="supplier_record_id" className="hms-label">Supplier Record ID (Read-only)</label>
                      <input
                        id="supplier_record_id"
                        className="hms-input bg-neutral-100"
                        value={editingItem.id}
                        readOnly
                      />
                    </div>
                    <div>
                      <label htmlFor="supplier_code_saved" className="hms-label">Supplier Code (Read-only)</label>
                      <input
                        id="supplier_code_saved"
                        className="hms-input bg-neutral-100"
                        value={supplierCodeDisplay}
                        readOnly
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label htmlFor="supplier_opening_balance" className="hms-label">Opening Balance (Read-only)</label>
                        <input
                          id="supplier_opening_balance"
                          className="hms-input bg-neutral-100"
                          value={`${editingItem.opening_balance ?? 0} ${(editingItem.opening_balance_type ?? 'cr').toUpperCase()}`}
                          readOnly
                        />
                      </div>
                      <div>
                        <label htmlFor="supplier_status" className="hms-label">Status (Read-only)</label>
                        <input
                          id="supplier_status"
                          className="hms-input bg-neutral-100"
                          value={editingItem.is_active ? 'Active' : 'Inactive'}
                          readOnly
                        />
                      </div>
                    </div>
                  </>
                )}
                <div>
                  <label htmlFor="supplier_code_preview" className="hms-label">
                    {editingItem ? 'Supplier Code Pattern Preview' : 'Supplier Code (Auto)'}
                  </label>
                  <input id="supplier_code_preview" className="hms-input bg-neutral-100" value={supplierCodePreview} readOnly />
                  <p className="mt-1 text-xs text-neutral-500">
                    {editingItem
                      ? 'Pattern preview based on current State/Country. Saved Supplier Code remains unchanged.'
                      : 'Prefix auto-fills from selected State/Country; running number is assigned on save.'}
                  </p>
                </div>
                <div>
                  <label htmlFor="supplier_director_name" className="hms-label">Company Director Name</label>
                  <input id="supplier_director_name" className="hms-input" placeholder="e.g. John Doe" {...register('company_director_name')} />
                </div>
                <div>
                  <label htmlFor="supplier_director_contact" className="hms-label">Company Director Contact</label>
                  <input id="supplier_director_contact" className="hms-input" placeholder="e.g. +91-9876543210" {...register('company_director_contact')} />
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
                  <label htmlFor="supplier_gstin_status" className="hms-label">GSTIN Status</label>
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
                  <label htmlFor="supplier_gstin" className="hms-label">{gstinStatus === 'registered' ? 'GSTIN *' : 'GSTIN'}</label>
                  {gstinStatus === 'registered' ? (
                    <input id="supplier_gstin" className="hms-input" placeholder="GSTIN" {...register('gstin')} />
                  ) : (
                    <div className="hms-input bg-neutral-100 text-neutral-500 flex items-center">NA</div>
                  )}
                </div>

                <div className="pt-2 border-t border-neutral-100">
                  <p className="text-xs font-bold uppercase tracking-wider text-neutral-500 mb-2">Billing Address</p>
                </div>
                <div>
                  <label htmlFor="supplier_address_line1" className="hms-label">Address</label>
                  <input id="supplier_address_line1" className="hms-input" placeholder="Address line 1" {...register('address_line1')} />
                </div>
                <div>
                  <label htmlFor="supplier_address_line2" className="hms-label">Address line 2</label>
                  <input id="supplier_address_line2" className="hms-input" placeholder="Address line 2" {...register('address_line2')} />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label htmlFor="supplier_city" className="hms-label">City</label>
                    <input id="supplier_city" className="hms-input" placeholder="City" {...register('city')} />
                  </div>
                  <div>
                    <label htmlFor="supplier_state" className="hms-label">State</label>
                    {isIndiaCountry ? (
                      <select id="supplier_state" className="hms-input" {...register('state')}>
                        <option value="">Select state</option>
                        {STATE_OPTIONS.map(({ state: stateValue, code }) => (
                          <option key={stateValue} value={stateValue}>
                            {stateValue.replace(/\b\w/g, (char) => char.toUpperCase())} ({code})
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input id="supplier_state" className="hms-input" placeholder="State / Province" {...register('state')} />
                    )}
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label htmlFor="supplier_state_code" className="hms-label">State Code</label>
                    <input
                      id="supplier_state_code"
                      className={isIndiaCountry ? 'hms-input bg-neutral-100' : 'hms-input'}
                      placeholder={isIndiaCountry ? 'Auto' : 'State code'}
                      readOnly={isIndiaCountry}
                      {...register('state_code')}
                    />
                  </div>
                  <div>
                    <label htmlFor="supplier_pincode" className="hms-label">Pincode</label>
                    <input id="supplier_pincode" className="hms-input" placeholder="Pincode" {...register('pincode')} />
                  </div>
                </div>
                <div>
                  <label htmlFor="supplier_country" className="hms-label">Country</label>
                  <select id="supplier_country" className="hms-input" {...register('billing_country')}>
                    {COUNTRIES.map((countryValue) => (
                      <option key={countryValue} value={countryValue}>{countryValue}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor="supplier_pos" className="hms-label">Place of Supply</label>
                  <input id="supplier_pos" className="hms-input" placeholder="e.g. Tamil Nadu" {...register('place_of_supply')} />
                </div>
                <div>
                  <label htmlFor="supplier_payment_terms" className="hms-label">Payment Terms (Days)</label>
                  <input id="supplier_payment_terms" type="number" min="0" className="hms-input" placeholder="e.g. 30" {...register('payment_terms_days')} />
                </div>
                <button type="submit" disabled={isSaving} className="w-full rounded-lg bg-primary px-5 py-2.5 text-sm font-bold text-white shadow-lg shadow-primary/20 transition hover:bg-primary/90 disabled:opacity-60">
                  {isSaving ? 'Saving...' : editingItem ? 'Update Supplier' : 'Create Supplier'}
                </button>
              </form>
            </div>
          )}
        </div>

        <div className="hms-card overflow-hidden">
          <div className="border-b border-neutral-200 px-5 py-4">
            <h2 className="font-display text-lg font-bold text-neutral-900">Suppliers</h2>
          </div>
          <div className="p-5">
          {!isLoading && !isError && (
            <div className="mb-4 space-y-3 rounded-lg border border-neutral-200 bg-neutral-50/70 p-3">
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
                <div className="xl:col-span-2">
                  <label htmlFor="supplier_list_search" className="hms-label">Search</label>
                  <input
                    id="supplier_list_search"
                    className="hms-input"
                    placeholder="Search by code, company, phone, contact, email"
                    value={searchTerm}
                    onChange={(event) => setSearchTerm(event.target.value)}
                  />
                </div>
                <div>
                  <label htmlFor="supplier_sort_by" className="hms-label">Sort By</label>
                  <select
                    id="supplier_sort_by"
                    className="hms-input"
                    value={sortBy}
                    onChange={(event) => setSortBy(event.target.value as SupplierSortField)}
                  >
                    <option value="created_at">Created Date</option>
                    <option value="company_name">Company</option>
                    <option value="supplier_code">Supplier ID</option>
                    <option value="phone">Phone</option>
                    <option value="gstin_status">GSTIN Status</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="supplier_sort_direction" className="hms-label">Order</label>
                  <select
                    id="supplier_sort_direction"
                    className="hms-input"
                    value={sortDirection}
                    onChange={(event) => setSortDirection(event.target.value as 'asc' | 'desc')}
                  >
                    <option value="desc">Descending</option>
                    <option value="asc">Ascending</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
                <div>
                  <label htmlFor="supplier_filter_gstin" className="hms-label">GSTIN Status</label>
                  <select
                    id="supplier_filter_gstin"
                    className="hms-input"
                    value={gstinFilter}
                    onChange={(event) => setGstinFilter(event.target.value as typeof gstinFilter)}
                  >
                    <option value="all">All</option>
                    <option value="registered">Registered</option>
                    <option value="non-registered">Non-Registered</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="supplier_filter_business" className="hms-label">Business Type</label>
                  <select
                    id="supplier_filter_business"
                    className="hms-input"
                    value={businessTypeFilter}
                    onChange={(event) => setBusinessTypeFilter(event.target.value as typeof businessTypeFilter)}
                  >
                    <option value="all">All</option>
                    <option value="domestic">Domestic</option>
                    <option value="international">International</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="supplier_filter_status" className="hms-label">Status</label>
                  <select
                    id="supplier_filter_status"
                    className="hms-input"
                    value={statusFilter}
                    onChange={(event) => setStatusFilter(event.target.value as typeof statusFilter)}
                  >
                    <option value="all">All</option>
                    <option value="active">Active</option>
                    <option value="inactive">Inactive</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="supplier_filter_created_from" className="hms-label">Created From</label>
                  <input
                    id="supplier_filter_created_from"
                    type="date"
                    className="hms-input"
                    value={createdFrom}
                    onChange={(event) => setCreatedFrom(event.target.value)}
                  />
                </div>
                <div>
                  <label htmlFor="supplier_filter_created_to" className="hms-label">Created To</label>
                  <input
                    id="supplier_filter_created_to"
                    type="date"
                    className="hms-input"
                    value={createdTo}
                    onChange={(event) => setCreatedTo(event.target.value)}
                  />
                </div>
              </div>

              <div className="flex items-center justify-between">
                <p className="text-xs text-neutral-500">Showing {filteredItems.length} of {items.length} suppliers</p>
                <button type="button" onClick={clearListFilters} className="rounded border border-neutral-200 bg-white px-3 py-1.5 text-xs font-semibold text-neutral-700 hover:bg-neutral-100">
                  Clear Filters
                </button>
              </div>
            </div>
          )}
          {isLoading && <PageLoading message="Loading suppliers..." />}
          {isError && <PageError message="Failed to load suppliers" />}
          {!isLoading && !isError && items.length === 0 && <PageEmpty message="No suppliers found" />}
          {!isLoading && !isError && items.length > 0 && filteredItems.length === 0 && <PageEmpty message="No suppliers match current filters" />}
          {!isLoading && !isError && filteredItems.length > 0 && (
            <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <caption className="sr-only">Suppliers list</caption>
              <thead className="bg-neutral-50">
                <tr className="text-left border-y border-neutral-200">
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Code</th>
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Company</th>
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Phone</th>
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">GSTIN</th>
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Created</th>
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {filteredItems.map((item) => (
                  <tr key={item.id} className="hover:bg-neutral-50/80">
                    <td className="px-4 py-3 font-mono text-xs">{item.supplier_code}</td>
                    <td className="px-4 py-3 font-medium">{item.company_name}</td>
                    <td className="px-4 py-3">{item.phone}</td>
                    <td className="px-4 py-3 font-mono text-xs">{item.gstin || '—'}</td>
                    <td className="px-4 py-3 text-xs text-neutral-600">{formatDisplayDate(item.created_at)}</td>
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
            </div>
            <div className="flex gap-3">
              <button 
                type="button" 
                onClick={() => setDeleteConfirm(null)}
                disabled={isDeleting}
                className="flex-1 rounded-lg border border-neutral-200 bg-white px-4 py-2.5 text-sm font-semibold text-neutral-600 transition hover:bg-neutral-50"
              >
                Cancel
              </button>
              <button 
                type="button" 
                onClick={() => deleteMutation.mutate(deleteConfirm)}
                disabled={isDeleting}
                className="flex-1 rounded-lg bg-red-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-red-600/20 transition hover:bg-red-700"
              >
                <span className="material-icons text-sm align-middle mr-1">delete</span>
                {isDeleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </AppLayout>
  );
};

export default SuppliersPage;
