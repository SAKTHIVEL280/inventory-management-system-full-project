import { type FocusEvent, useEffect, useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { customersApi } from '../api/customers';
import { companyApi } from '../api/company';
import { Company, Customer } from '../types';
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

const toTitleCase = (value: string): string =>
  value.replace(/\b\w/g, (char) => char.toUpperCase());

const DEFAULT_COUNTRIES = ['India', 'United States', 'United Arab Emirates', 'United Kingdom', 'Singapore', 'Australia'];
const DEFAULT_CURRENCIES = ['INR', 'USD', 'EUR', 'GBP'];
const DEFAULT_STATES = STATE_OPTIONS.map(({ state }) => toTitleCase(state));
const DEFAULT_PHONE_COUNTRY_CODES = ['+91', '+66', '+65', '+44'];
const KNOWN_PHONE_COUNTRY_CODE_DIGITS = [
  '1', '7', '20', '27', '30', '31', '32', '33', '34', '36', '39', '40', '41', '43', '44', '45', '46', '47', '48', '49',
  '51', '52', '53', '54', '55', '56', '57', '58', '60', '61', '62', '63', '64', '65', '66', '81', '82', '84', '86', '90',
  '91', '92', '93', '94', '95', '98', '211', '212', '213', '216', '218', '220', '221', '222', '223', '224', '225', '226',
  '227', '228', '229', '230', '231', '232', '233', '234', '235', '236', '237', '238', '239', '240', '241', '242', '243',
  '244', '245', '246', '247', '248', '249', '250', '251', '252', '253', '254', '255', '256', '257', '258', '260', '261',
  '262', '263', '264', '265', '266', '267', '268', '269', '290', '291', '297', '298', '299', '350', '351', '352', '353',
  '354', '355', '356', '357', '358', '359', '370', '371', '372', '373', '374', '375', '376', '377', '378', '380', '381',
  '382', '383', '385', '386', '387', '389', '420', '421', '423', '500', '501', '502', '503', '504', '505', '506', '507',
  '508', '509', '590', '591', '592', '593', '594', '595', '596', '597', '598', '599', '670', '672', '673', '674', '675',
  '676', '677', '678', '679', '680', '681', '682', '683', '685', '686', '687', '688', '689', '690', '691', '692', '850',
  '852', '853', '855', '856', '880', '886', '960', '961', '962', '963', '964', '965', '966', '967', '968', '970', '971',
  '972', '973', '974', '975', '976', '977', '992', '993', '994', '995', '996', '998',
].sort((left, right) => right.length - left.length || left.localeCompare(right));

const schema = z.object({
  company_name: z.string().min(1, 'Company name required'),
  phone: z.string().min(1, 'Phone number required').regex(/^\d+$/, 'Phone number must contain digits only'),
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
  shipping_address_line1: z.string().optional(),
  shipping_address_line2: z.string().optional(),
  shipping_city: z.string().optional(),
  shipping_state: z.string().optional(),
  shipping_state_code: z.string().optional(),
  shipping_country: z.string().optional(),
  shipping_pincode: z.string().optional(),
  payment_terms_days: z.preprocess(
    (value) => {
      if (value === '' || value === null || value === undefined) return undefined;
      return Number(value);
    },
    z.number().min(0, 'Cannot be negative').optional()
  ),
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
type CustomerSortField = 'created_at' | 'company_name' | 'customer_code' | 'phone' | 'customer_type';

const formatDisplayDate = (value?: string | null): string => {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '—';
  return parsed.toLocaleDateString();
};

const normalizeOptional = (value?: string): string | null => value?.trim() || null;

const normalizeStateCodeOptional = (value?: string): string | null => {
  const trimmed = (value || '').trim();
  return trimmed ? trimmed.toUpperCase() : null;
};

const normalizePhoneDigits = (value?: string): string => (value || '').replace(/\D/g, '');

const normalizePhoneCountryCode = (value?: string): string => {
  const digits = normalizePhoneDigits(value);
  return digits ? `+${digits}` : '+';
};

const parsePhoneForEditing = (storedPhone?: string | null): { code: string; localNumber: string } => {
  const normalized = (storedPhone || '').replace(/\s+/g, '');
  if (!normalized) {
    return { code: '+91', localNumber: '' };
  }

  if (normalized.startsWith('+')) {
    const digits = normalizePhoneDigits(normalized.slice(1));
    const matchedCode = KNOWN_PHONE_COUNTRY_CODE_DIGITS.find((code) => digits.startsWith(code));
    if (matchedCode) {
      return {
        code: `+${matchedCode}`,
        localNumber: digits.slice(matchedCode.length),
      };
    }
  }

  for (const code of DEFAULT_PHONE_COUNTRY_CODES) {
    if (normalized.startsWith(code)) {
      return {
        code,
        localNumber: normalizePhoneDigits(normalized.slice(code.length)),
      };
    }
  }

  const fallback = /^\+(\d{1,3})(\d+)$/u.exec(normalized);
  if (fallback) {
    return {
      code: `+${fallback[1]}`,
      localNumber: fallback[2],
    };
  }

  return {
    code: '+91',
    localNumber: normalizePhoneDigits(normalized),
  };
};

const buildDefaultValues = (companyProfile?: Company): CustomerForm => ({
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
  billing_address_line1: companyProfile?.address_line1 ?? '',
  billing_address_line2: companyProfile?.address_line2 ?? '',
  billing_city: companyProfile?.city ?? '',
  billing_state: companyProfile?.state ?? '',
  billing_state_code: companyProfile?.state_code ?? '',
  billing_country: 'India',
  billing_pincode: companyProfile?.pincode ?? '',
  same_as_billing: true,
  shipping_address_line1: '',
  shipping_address_line2: '',
  shipping_city: '',
  shipping_state: '',
  shipping_state_code: '',
  shipping_country: '',
  shipping_pincode: '',
  payment_terms_days: undefined,
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

type TypeaheadInputProps = {
  id: string;
  value: string;
  options: string[];
  placeholder: string;
  onChange: (nextValue: string) => void;
  className?: string;
  showAllWhenFocused?: boolean;
};

const TypeaheadInput = ({
  id,
  value,
  options,
  placeholder,
  onChange,
  className = 'hms-input',
  showAllWhenFocused = false,
}: TypeaheadInputProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const [hasTypedSinceFocus, setHasTypedSinceFocus] = useState(false);

  const filteredOptions = useMemo(() => {
    const needle = showAllWhenFocused && !hasTypedSinceFocus
      ? ''
      : value.trim().toLowerCase();
    const base = options
      .map((option) => option.trim())
      .filter((option) => option.length > 0);

    if (!needle) {
      return [...new Set(base)].slice(0, 10);
    }

    const startsWithMatches = base.filter((option) => option.toLowerCase().startsWith(needle));
    const includesMatches = base.filter(
      (option) => !option.toLowerCase().startsWith(needle) && option.toLowerCase().includes(needle)
    );

    return [...new Set([...startsWithMatches, ...includesMatches])].slice(0, 10);
  }, [hasTypedSinceFocus, options, showAllWhenFocused, value]);

  return (
    <div className="relative">
      <input
        id={id}
        className={className}
        value={value}
        placeholder={placeholder}
        onFocus={() => {
          setHasTypedSinceFocus(false);
          setIsOpen(true);
        }}
        onBlur={() => {
          window.setTimeout(() => setIsOpen(false), 120);
          setHasTypedSinceFocus(false);
        }}
        onChange={(event) => {
          setHasTypedSinceFocus(true);
          onChange(event.target.value);
          setIsOpen(true);
        }}
      />
      {isOpen && filteredOptions.length > 0 && (
        <div className="absolute z-20 mt-1 max-h-52 w-full overflow-auto rounded-lg border border-neutral-200 bg-white shadow-lg">
          {filteredOptions.map((option) => (
            <button
              key={`${id}-${option}`}
              type="button"
              className="block w-full px-3 py-2 text-left text-sm text-neutral-700 hover:bg-neutral-100"
              onMouseDown={(event) => {
                event.preventDefault();
                onChange(option);
                setHasTypedSinceFocus(false);
                setIsOpen(false);
              }}
            >
              {option}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

const CustomersPage = () => {
  const queryClient = useQueryClient();
  const [editingItem, setEditingItem] = useState<Customer | null>(null);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState<CustomerSortField>('created_at');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');
  const [customerTypeFilter, setCustomerTypeFilter] = useState<'all' | 'regular' | 'dealer' | 'distributor' | 'retail'>('all');
  const [businessTypeFilter, setBusinessTypeFilter] = useState<'all' | 'domestic' | 'international'>('all');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all');
  const [createdFrom, setCreatedFrom] = useState('');
  const [createdTo, setCreatedTo] = useState('');
  const [phoneCountryCode, setPhoneCountryCode] = useState('+91');

  const { data, isLoading, isError } = useQuery({
    queryKey: ['customers'],
    queryFn: () => customersApi.list({ page: 1, page_size: 500 }),
  });

  const { data: customizationOptions } = useQuery({
    queryKey: ['customer-customization-options'],
    queryFn: async () => {
      try {
        return await customersApi.getCustomizationOptions();
      } catch {
        return { countries: DEFAULT_COUNTRIES, currencies: DEFAULT_CURRENCIES, states: DEFAULT_STATES };
      }
    },
  });

  const { data: companyProfile } = useQuery({
    queryKey: ['company-profile'],
    queryFn: async () => {
      try {
        return await companyApi.get();
      } catch {
        return null;
      }
    },
  });

  const { register, handleSubmit, reset, setValue, watch } = useForm<CustomerForm>({
    defaultValues: buildDefaultValues(),
  });

  useEffect(() => {
    if (!editingItem && !isFormOpen) {
      reset(buildDefaultValues(companyProfile ?? undefined));
    }
  }, [companyProfile, editingItem, isFormOpen, reset]);

  const createMutation = useMutation({
    mutationFn: customersApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customers'] });
      queryClient.invalidateQueries({ queryKey: ['customer-customization-options'] });
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
      queryClient.invalidateQueries({ queryKey: ['customer-customization-options'] });
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
    reset(buildDefaultValues(companyProfile ?? undefined));
    setPhoneCountryCode('+91');
    setIsFormOpen(false);
  };

  const startEdit = (item: Customer) => {
    const parsedPhone = parsePhoneForEditing(item.phone);
    setPhoneCountryCode(normalizePhoneCountryCode(parsedPhone.code));
    setEditingItem(item);
    setIsFormOpen(true);
    setValue('company_name', item.company_name);
    setValue('phone', parsedPhone.localNumber);
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
    setValue('billing_country', item.billing_country ?? '');
    setValue('billing_pincode', item.billing_pincode ?? '');
    setValue('same_as_billing', item.same_as_billing ?? true);
    setValue('shipping_address_line1', item.shipping_address_line1 ?? '');
    setValue('shipping_address_line2', item.shipping_address_line2 ?? '');
    setValue('shipping_city', item.shipping_city ?? '');
    setValue('shipping_state', item.shipping_state ?? '');
    setValue('shipping_state_code', item.shipping_state_code ?? '');
    setValue('shipping_country', item.shipping_country ?? '');
    setValue('shipping_pincode', item.shipping_pincode ?? '');
    setValue('payment_terms_days', item.payment_terms_days ?? undefined);
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

    const normalizedPhone = normalizePhoneDigits(parsed.data.phone);
    const normalizedCode = normalizePhoneCountryCode(phoneCountryCode);
    const countryCodeDigits = normalizePhoneDigits(normalizedCode);
    if (!countryCodeDigits) {
      showError('Country code is required.');
      return;
    }
    const totalDigits = countryCodeDigits.length + normalizedPhone.length;
    if (totalDigits < 6 || totalDigits > 15) {
      showError('Phone number must contain 6 to 15 digits including country code.');
      return;
    }

    const finalPhone = `${normalizedCode}${normalizedPhone}`;

    const payload = {
      company_name: parsed.data.company_name.trim(),
      company_director_name: normalizeOptional(parsed.data.company_director_name),
      company_director_contact: normalizeOptional(parsed.data.company_director_contact),
      contact_person: normalizeOptional(parsed.data.contact_person),
      email: normalizeOptional(parsed.data.email),
      phone: finalPhone,
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
      billing_state_code: normalizeStateCodeOptional(parsed.data.billing_state_code),
      billing_country: normalizeOptional(parsed.data.billing_country),
      billing_pincode: normalizeOptional(parsed.data.billing_pincode),
      same_as_billing: parsed.data.same_as_billing ?? true,
      shipping_address_line1: parsed.data.same_as_billing ? null : normalizeOptional(parsed.data.shipping_address_line1),
      shipping_address_line2: parsed.data.same_as_billing ? null : normalizeOptional(parsed.data.shipping_address_line2),
      shipping_city: parsed.data.same_as_billing ? null : normalizeOptional(parsed.data.shipping_city),
      shipping_state: parsed.data.same_as_billing ? null : normalizeOptional(parsed.data.shipping_state),
      shipping_state_code: parsed.data.same_as_billing ? null : normalizeStateCodeOptional(parsed.data.shipping_state_code),
      shipping_country: parsed.data.same_as_billing ? null : normalizeOptional(parsed.data.shipping_country),
      shipping_pincode: parsed.data.same_as_billing ? null : normalizeOptional(parsed.data.shipping_pincode),
      credit_limit: parsed.data.credit_limit,
      payment_terms_days: parsed.data.payment_terms_days ?? null,
      currency_code: parsed.data.currency_code.trim().toUpperCase() || 'INR',
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

  const items = useMemo(() => data?.items ?? [], [data?.items]);
  const filteredItems = useMemo(() => {
    const normalizedSearch = searchTerm.trim().toLowerCase();
    const fromTime = createdFrom ? new Date(`${createdFrom}T00:00:00`).getTime() : null;
    const toTime = createdTo ? new Date(`${createdTo}T23:59:59.999`).getTime() : null;

    const filtered = items.filter((item) => {
      if (normalizedSearch) {
        const haystack = [
          item.customer_code ?? '',
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

      if (customerTypeFilter !== 'all' && item.customer_type !== customerTypeFilter) {
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
    customerTypeFilter,
    items,
    searchTerm,
    sortBy,
    sortDirection,
    statusFilter,
  ]);
  const isSaving = createMutation.isPending || updateMutation.isPending;
  const businessType = watch('business_type');
  const gstinStatus = watch('gstin_status');
  const currencyCodeValue = watch('currency_code') ?? 'INR';
  const billingStateValue = watch('billing_state') ?? '';
  const shippingStateValue = watch('shipping_state') ?? '';
  const billingStateCode = watch('billing_state_code');
  const billingCountryValue = watch('billing_country') ?? '';
  const sameAsBilling = watch('same_as_billing');
  const shippingCountryValue = watch('shipping_country') ?? '';
  const customerCodePreview = toCustomerCodePreview(businessType, billingStateValue, billingStateCode, billingCountryValue);
  const customerCodeDisplay = editingItem?.customer_code || customerCodePreview;

  const clearListFilters = () => {
    setSearchTerm('');
    setSortBy('created_at');
    setSortDirection('desc');
    setCustomerTypeFilter('all');
    setBusinessTypeFilter('all');
    setStatusFilter('all');
    setCreatedFrom('');
    setCreatedTo('');
  };

  const countryOptions = useMemo(() => {
    const merged = [...DEFAULT_COUNTRIES, ...(customizationOptions?.countries ?? [])]
      .map((country) => country.trim())
      .filter((country) => country.length > 0);
    return [...new Set(merged)].sort((left, right) => left.localeCompare(right));
  }, [customizationOptions]);

  const currencyOptions = useMemo(() => {
    const merged = [...DEFAULT_CURRENCIES, ...(customizationOptions?.currencies ?? [])]
      .map((currency) => currency.trim().toUpperCase())
      .filter((currency) => currency.length > 0);
    return [...new Set(merged)].sort((left, right) => left.localeCompare(right));
  }, [customizationOptions]);

  const stateOptions = useMemo(() => {
    const merged = [...DEFAULT_STATES, ...(customizationOptions?.states ?? [])]
      .map((state) => state.trim())
      .filter((state) => state.length > 0);
    return [...new Set(merged)].sort((left, right) => left.localeCompare(right));
  }, [customizationOptions]);

  const phoneCountryCodeOptions = useMemo(() => {
    const merged = [
      ...DEFAULT_PHONE_COUNTRY_CODES,
      ...items.map((item) => parsePhoneForEditing(item.phone).code),
      phoneCountryCode,
    ]
      .map((code) => normalizePhoneCountryCode(code))
      .filter((code) => code !== '+');

    return [...new Set(merged)].sort((left, right) => left.localeCompare(right, undefined, { numeric: true }));
  }, [items, phoneCountryCode]);

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
                      reset(buildDefaultValues(companyProfile ?? undefined));
                      setPhoneCountryCode('+91');
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
                {editingItem && (
                  <>
                    <div>
                      <label htmlFor="customer_code_saved" className="hms-label">Customer ID (Read-only)</label>
                      <input
                        id="customer_code_saved"
                        className="hms-input bg-neutral-100"
                        value={customerCodeDisplay}
                        readOnly
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label htmlFor="customer_opening_balance" className="hms-label">Opening Balance (Read-only)</label>
                        <input
                          id="customer_opening_balance"
                          className="hms-input bg-neutral-100"
                          value={`${editingItem.opening_balance ?? 0} ${(editingItem.opening_balance_type ?? 'dr').toUpperCase()}`}
                          readOnly
                        />
                      </div>
                      <div>
                        <label htmlFor="customer_status" className="hms-label">Status (Read-only)</label>
                        <input
                          id="customer_status"
                          className="hms-input bg-neutral-100"
                          value={editingItem.is_active ? 'Active' : 'Inactive'}
                          readOnly
                        />
                      </div>
                    </div>
                  </>
                )}
                <div>
                  <label htmlFor="customer_code_preview" className="hms-label">
                    {editingItem ? 'Customer ID Pattern Preview' : 'Customer ID (Auto)'}
                  </label>
                  <input id="customer_code_preview" className="hms-input bg-neutral-100" value={customerCodePreview} readOnly />
                  <p className="mt-1 text-xs text-neutral-500">
                    {editingItem
                      ? 'Pattern preview based on current State/Country. Saved Customer ID remains unchanged.'
                      : 'Prefix auto-fills from selected State/Country; running number is assigned on save.'}
                  </p>
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
                  <label className="hms-label">Phone</label>
                  <div className="grid grid-cols-3 gap-2">
                    <div>
                      <label htmlFor="phone_country_code" className="sr-only">Country code</label>
                      <TypeaheadInput
                        id="phone_country_code"
                        value={phoneCountryCode}
                        options={phoneCountryCodeOptions}
                        placeholder="Type country code"
                        showAllWhenFocused
                        onChange={(nextValue) => {
                          setPhoneCountryCode(normalizePhoneCountryCode(nextValue));
                        }}
                      />
                    </div>
                    <div className="col-span-2">
                      <label htmlFor="phone" className="sr-only">Phone number</label>
                      <input
                        id="phone"
                        type="tel"
                        className="hms-input"
                        placeholder="Enter phone number"
                        autoComplete="tel"
                        {...register('phone')}
                      />
                    </div>
                  </div>
                  <p className="mt-1 text-xs text-neutral-500">Supports 6 to 15 digits; country prefix available (+91, +66, +65).</p>
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
                  <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Payment Terms (Days)</label><input type="number" min="0" className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" placeholder="e.g. 30" {...register('payment_terms_days')} /></div>
                  <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Credit Limit in Currency</label><input type="number" min="0" className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" {...register('credit_limit')} onFocus={clearZeroOnFocus} /></div>
                    <div>
                      <label htmlFor="currency_code" className="mb-1 block text-sm font-semibold text-neutral-700">Currency</label>
                      <input type="hidden" {...register('currency_code')} />
                      <TypeaheadInput
                        id="currency_code"
                        value={currencyCodeValue}
                        options={currencyOptions}
                        placeholder="Type currency code (e.g. INR)"
                        className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm"
                        onChange={(nextValue) => {
                          setValue('currency_code', nextValue.toUpperCase(), { shouldDirty: true });
                        }}
                      />
                    </div>
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
                    <input type="hidden" {...register('billing_state')} />
                    <TypeaheadInput
                      id="billing_state"
                      value={billingStateValue}
                      options={stateOptions}
                      placeholder="Type or select state"
                      onChange={(nextValue) => {
                        setValue('billing_state', nextValue, { shouldDirty: true });
                      }}
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label htmlFor="billing_state_code" className="hms-label">State Code</label>
                    <input id="billing_state_code" className="hms-input" placeholder="e.g. 29 or N/A" maxLength={5} {...register('billing_state_code')} />
                  </div>
                  <div>
                    <label htmlFor="billing_pincode" className="hms-label">Pincode</label>
                    <input id="billing_pincode" className="hms-input" placeholder="Pincode" {...register('billing_pincode')} />
                  </div>
                </div>
                <div>
                  <label htmlFor="billing_country" className="hms-label">Country</label>
                  <input type="hidden" {...register('billing_country')} />
                  <TypeaheadInput
                    id="billing_country"
                    value={billingCountryValue}
                    options={countryOptions}
                    placeholder="Type or select country"
                    onChange={(nextValue) => {
                      setValue('billing_country', nextValue, { shouldDirty: true });
                    }}
                  />
                </div>
                <div className="flex items-center gap-2">
                  <input id="same_as_billing" type="checkbox" className="rounded border-neutral-300" {...register('same_as_billing')} />
                  <label htmlFor="same_as_billing" className="text-sm text-neutral-600">Shipping same as billing</label>
                </div>
                {!sameAsBilling && (
                  <>
                    <div className="pt-2 border-t border-neutral-100">
                      <p className="text-xs font-bold uppercase tracking-wider text-neutral-500 mb-2">Shipping Address</p>
                    </div>
                    <div>
                      <label htmlFor="shipping_address_line1" className="hms-label">Address</label>
                      <input id="shipping_address_line1" className="hms-input" placeholder="Shipping address line 1" {...register('shipping_address_line1')} />
                    </div>
                    <div>
                      <label htmlFor="shipping_address_line2" className="hms-label">Address line 2</label>
                      <input id="shipping_address_line2" className="hms-input" placeholder="Shipping address line 2" {...register('shipping_address_line2')} />
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label htmlFor="shipping_city" className="hms-label">City</label>
                        <input id="shipping_city" className="hms-input" placeholder="City" {...register('shipping_city')} />
                      </div>
                      <div>
                        <label htmlFor="shipping_state" className="hms-label">State</label>
                        <input type="hidden" {...register('shipping_state')} />
                        <TypeaheadInput
                          id="shipping_state"
                          value={shippingStateValue}
                          options={stateOptions}
                          placeholder="Type or select state"
                          onChange={(nextValue) => {
                            setValue('shipping_state', nextValue, { shouldDirty: true });
                          }}
                        />
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label htmlFor="shipping_state_code" className="hms-label">State Code</label>
                        <input id="shipping_state_code" className="hms-input" placeholder="e.g. 29 or N/A" maxLength={5} {...register('shipping_state_code')} />
                      </div>
                      <div>
                        <label htmlFor="shipping_pincode" className="hms-label">Pincode</label>
                        <input id="shipping_pincode" className="hms-input" placeholder="Pincode" {...register('shipping_pincode')} />
                      </div>
                    </div>
                    <div>
                      <label htmlFor="shipping_country" className="hms-label">Country</label>
                      <input type="hidden" {...register('shipping_country')} />
                      <TypeaheadInput
                        id="shipping_country"
                        value={shippingCountryValue}
                        options={countryOptions}
                        placeholder="Type or select country"
                        onChange={(nextValue) => {
                          setValue('shipping_country', nextValue, { shouldDirty: true });
                        }}
                      />
                    </div>
                  </>
                )}
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
          {!isLoading && !isError && (
            <div className="mb-4 space-y-3 rounded-lg border border-neutral-200 bg-neutral-50/70 p-3">
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
                <div className="xl:col-span-2">
                  <label htmlFor="customer_list_search" className="hms-label">Search</label>
                  <input
                    id="customer_list_search"
                    className="hms-input"
                    placeholder="Search by code, company, phone, contact, email"
                    value={searchTerm}
                    onChange={(event) => setSearchTerm(event.target.value)}
                  />
                </div>
                <div>
                  <label htmlFor="customer_sort_by" className="hms-label">Sort By</label>
                  <select
                    id="customer_sort_by"
                    className="hms-input"
                    value={sortBy}
                    onChange={(event) => setSortBy(event.target.value as CustomerSortField)}
                  >
                    <option value="created_at">Created Date</option>
                    <option value="company_name">Company</option>
                    <option value="customer_code">Customer ID</option>
                    <option value="phone">Phone</option>
                    <option value="customer_type">Customer Type</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="customer_sort_direction" className="hms-label">Order</label>
                  <select
                    id="customer_sort_direction"
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
                  <label htmlFor="customer_filter_type" className="hms-label">Customer Type</label>
                  <select
                    id="customer_filter_type"
                    className="hms-input"
                    value={customerTypeFilter}
                    onChange={(event) => setCustomerTypeFilter(event.target.value as typeof customerTypeFilter)}
                  >
                    <option value="all">All</option>
                    <option value="regular">Regular</option>
                    <option value="dealer">Dealer</option>
                    <option value="distributor">Distributor</option>
                    <option value="retail">Retail</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="customer_filter_business" className="hms-label">Business Type</label>
                  <select
                    id="customer_filter_business"
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
                  <label htmlFor="customer_filter_status" className="hms-label">Status</label>
                  <select
                    id="customer_filter_status"
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
                  <label htmlFor="customer_filter_created_from" className="hms-label">Created From</label>
                  <input
                    id="customer_filter_created_from"
                    type="date"
                    className="hms-input"
                    value={createdFrom}
                    onChange={(event) => setCreatedFrom(event.target.value)}
                  />
                </div>
                <div>
                  <label htmlFor="customer_filter_created_to" className="hms-label">Created To</label>
                  <input
                    id="customer_filter_created_to"
                    type="date"
                    className="hms-input"
                    value={createdTo}
                    onChange={(event) => setCreatedTo(event.target.value)}
                  />
                </div>
              </div>

              <div className="flex items-center justify-between">
                <p className="text-xs text-neutral-500">Showing {filteredItems.length} of {items.length} customers</p>
                <button type="button" onClick={clearListFilters} className="rounded border border-neutral-200 bg-white px-3 py-1.5 text-xs font-semibold text-neutral-700 hover:bg-neutral-100">
                  Clear Filters
                </button>
              </div>
            </div>
          )}
          {isLoading && <PageLoading message="Loading customers..." />}
          {isError && <PageError message="Failed to load customers" />}
          {!isLoading && !isError && items.length === 0 && <PageEmpty message="No customers found" />}
          {!isLoading && !isError && items.length > 0 && filteredItems.length === 0 && <PageEmpty message="No customers match current filters" />}
          {!isLoading && !isError && filteredItems.length > 0 && (
            <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <caption className="sr-only">Customers list</caption>
              <thead className="bg-neutral-50">
                <tr className="text-left border-y border-neutral-200">
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Code</th>
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Company</th>
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Phone</th>
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Type</th>
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Created</th>
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {filteredItems.map((item) => (
                  <tr key={item.id} className="hover:bg-neutral-50/80">
                    <td className="px-4 py-3 font-mono text-xs">{item.customer_code}</td>
                    <td className="px-4 py-3 font-medium">{item.company_name}</td>
                    <td className="px-4 py-3">{item.phone}</td>
                    <td className="px-4 py-3">
                      <span className="rounded-full bg-blue-100 px-2.5 py-1 text-xs font-bold uppercase tracking-wide text-blue-700">
                        {item.customer_type}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-neutral-600">{formatDisplayDate(item.created_at)}</td>
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
