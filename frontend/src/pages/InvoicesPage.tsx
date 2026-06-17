/**
 * Sales Invoices Page
 * List, create, edit, issue invoices. GST-aware line items.
 */
import { useState, useEffect, useCallback, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { AppLayout } from '../components/AppLayout';
import { salesApi, type SalesInvoice, type CreateInvoicePayload, type SalesLineItem, type SalesInvoiceItem, type InvoiceTypeValue, type InvoiceBatchOption } from '../api/sales';
import { stockistsApi, salesManagersApi } from '../api/masterData';
import { apiClient } from '../api/client';
import { toast } from 'sonner';
import { confirmWithToast } from '../utils/toastHelper';
import { addDaysToDateInputValue, todayLocalDateInputValue } from '../utils/date';
import { emptyWhenZero } from '../utils/numberInput';
import { usePermissions } from '../hooks/usePermissions';
import type { Stockist, SalesManager } from '../types';

interface ProductOption { id: string; name: string; product_code: string; sku?: string | null; selling_price: number; mrp: number; gst_rate: number; hsn_code: string; description?: string; uom_id?: string | null; alt_uom_id?: string | null; }
interface CustomerOption {
  id: string;
  company_name: string;
  customer_code: string;
  payment_terms_days?: number;
  billing_state?: string;
  billing_state_code?: string;
  billing_country?: string;
  shipping_state?: string;
  shipping_state_code?: string;
  shipping_country?: string;
}
interface CompanyLocation { state?: string; state_code?: string; }
interface UomOption { id: string; name: string; abbreviation: string; }

const INVOICE_TYPE_LABELS: Record<InvoiceTypeValue, string> = {
  export_invoice: 'Export Invoice',
  within_state: 'Sales Invoice - Within State',
  other_states: 'Sales Invoice - Other States',
  union_territory: 'Sales Invoice - Union Territory',
};

const INVOICE_TYPE_OPTIONS: Array<{ value: InvoiceTypeValue; label: string }> = [
  { value: 'export_invoice', label: INVOICE_TYPE_LABELS.export_invoice },
  { value: 'within_state', label: INVOICE_TYPE_LABELS.within_state },
  { value: 'other_states', label: INVOICE_TYPE_LABELS.other_states },
  { value: 'union_territory', label: INVOICE_TYPE_LABELS.union_territory },
];

const UNION_TERRITORY_CODES = new Set(['01', '04', '07', '26', '31', '34', '35', '37', '38']);
const UNION_TERRITORY_NAMES = new Set([
  'andaman and nicobar islands',
  'chandigarh',
  'dadra and nagar haveli and daman and diu',
  'delhi',
  'jammu and kashmir',
  'ladakh',
  'lakshadweep',
  'pondicherry',
  'puducherry',
]);

const STATE_CODE_ENTRIES: Array<[string, string, string]> = [
  ['01', 'JK', 'jammu and kashmir'],
  ['02', 'HP', 'himachal pradesh'],
  ['03', 'PB', 'punjab'],
  ['04', 'CH', 'chandigarh'],
  ['05', 'UK', 'uttarakhand'],
  ['06', 'HR', 'haryana'],
  ['07', 'DL', 'delhi'],
  ['08', 'RJ', 'rajasthan'],
  ['09', 'UP', 'uttar pradesh'],
  ['10', 'BR', 'bihar'],
  ['11', 'SK', 'sikkim'],
  ['12', 'AR', 'arunachal pradesh'],
  ['13', 'NL', 'nagaland'],
  ['14', 'MN', 'manipur'],
  ['15', 'MZ', 'mizoram'],
  ['16', 'TR', 'tripura'],
  ['17', 'ML', 'meghalaya'],
  ['18', 'AS', 'assam'],
  ['19', 'WB', 'west bengal'],
  ['20', 'JH', 'jharkhand'],
  ['21', 'OR', 'odisha'],
  ['22', 'CT', 'chhattisgarh'],
  ['23', 'MP', 'madhya pradesh'],
  ['24', 'GJ', 'gujarat'],
  ['26', 'DD', 'dadra and nagar haveli and daman and diu'],
  ['27', 'MH', 'maharashtra'],
  ['28', 'AP', 'andhra pradesh'],
  ['29', 'KA', 'karnataka'],
  ['30', 'GA', 'goa'],
  ['31', 'LD', 'lakshadweep'],
  ['32', 'KL', 'kerala'],
  ['33', 'TN', 'tamil nadu'],
  ['34', 'PY', 'puducherry'],
  ['35', 'AN', 'andaman and nicobar islands'],
  ['36', 'TS', 'telangana'],
  ['37', 'LA', 'ladakh'],
  ['38', 'LA', 'ladakh'],
];

const STATE_CODE_MAP = STATE_CODE_ENTRIES.reduce<Record<string, string>>((acc, [numericCode, abbreviation, stateName]) => {
  acc[numericCode] = numericCode;
  acc[abbreviation] = numericCode;
  acc[stateName] = numericCode;
  return acc;
}, {});

const normalizeTextToken = (value?: string | null) => (value || '').trim().toLowerCase().replace(/\s+/g, ' ');
const normalizeStateCodeToken = (value?: string | null) => {
  const raw = (value || '').trim();
  if (!raw) return '';

  const normalizedName = normalizeTextToken(raw);
  if (STATE_CODE_MAP[normalizedName]) return STATE_CODE_MAP[normalizedName];

  const upperRaw = raw.toUpperCase();
  if (/^\d+$/.test(upperRaw)) {
    const padded = upperRaw.padStart(2, '0');
    return STATE_CODE_MAP[padded] || padded;
  }

  return STATE_CODE_MAP[upperRaw] || upperRaw;
};
const isIndiaCountry = (value?: string | null) => {
  const token = normalizeTextToken(value);
  return token === 'india' || token === 'in' || token === 'bharat' || token === 'republic of india';
};

const extractApiMessages = (detail: unknown): string[] => {
  if (!detail) return [];
  if (typeof detail === 'string') return [detail];
  if (Array.isArray(detail)) {
    return detail
      .flatMap((entry) => {
        if (typeof entry === 'string') return [entry];
        if (entry && typeof entry === 'object') {
          const obj = entry as { msg?: string; message?: string };
          return [obj.msg || obj.message || ''];
        }
        return [''];
      })
      .map((msg) => msg.trim())
      .filter(Boolean);
  }
  if (detail && typeof detail === 'object') {
    const obj = detail as { message?: string; messages?: unknown[]; detail?: unknown };
    if (Array.isArray(obj.messages)) {
      return extractApiMessages(obj.messages);
    }
    if (obj.detail) {
      return extractApiMessages(obj.detail);
    }
    if (typeof obj.message === 'string' && obj.message.trim()) {
      return [obj.message.trim()];
    }
  }
  return [];
};

// Searchable single-select (type-ahead) constrained to the provided options.
// Used for the mandatory Stockist Name / Sales Manager Name lookups (FR-17).
type SearchableSelectProps = {
  value: string;
  options: string[];
  placeholder: string;
  onChange: (next: string) => void;
  disabled?: boolean;
  className?: string;
};

const SearchableSelect = ({ value, options, placeholder, onChange, disabled, className }: SearchableSelectProps) => {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const base = options.map((o) => o.trim()).filter(Boolean);
    if (!needle) return [...new Set(base)].slice(0, 50);
    const starts = base.filter((o) => o.toLowerCase().startsWith(needle));
    const includes = base.filter((o) => !o.toLowerCase().startsWith(needle) && o.toLowerCase().includes(needle));
    return [...new Set([...starts, ...includes])].slice(0, 50);
  }, [options, query]);

  return (
    <div className="relative">
      <input
        className={className || 'w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm'}
        value={open ? query : value}
        placeholder={placeholder}
        disabled={disabled}
        autoComplete="off"
        onFocus={() => { setQuery(''); setOpen(true); }}
        onBlur={() => { window.setTimeout(() => setOpen(false), 150); }}
        onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
      />
      {open && !disabled && (
        <div className="absolute z-30 mt-1 max-h-52 w-full overflow-auto rounded-lg border border-neutral-200 bg-white shadow-lg">
          {filtered.length === 0 ? (
            <div className="px-3 py-2 text-sm text-neutral-400">No matches</div>
          ) : (
            filtered.map((option) => (
              <button
                key={option}
                type="button"
                className="block w-full px-3 py-2 text-left text-sm text-neutral-700 hover:bg-neutral-100"
                onMouseDown={(e) => { e.preventDefault(); onChange(option); setOpen(false); }}
              >
                {option}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
};

// Multi-select dropdown filter (checkbox list) for Stockist / Sales Manager.
type MultiSelectFilterProps = {
  label: string;
  options: string[];
  selected: string[];
  onChange: (next: string[]) => void;
};

const MultiSelectFilter = ({ label, options, selected, onChange }: MultiSelectFilterProps) => {
  const [open, setOpen] = useState(false);
  const toggle = (value: string) => {
    if (selected.includes(value)) onChange(selected.filter((v) => v !== value));
    else onChange([...selected, value]);
  };
  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        onBlur={() => window.setTimeout(() => setOpen(false), 150)}
        className="inline-flex items-center gap-1 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700 hover:bg-neutral-50"
      >
        {label}{selected.length > 0 ? ` (${selected.length})` : ''}
        <span className="material-icons text-base" aria-hidden="true">arrow_drop_down</span>
      </button>
      {open && (
        <div className="absolute z-30 mt-1 max-h-64 w-56 overflow-auto rounded-lg border border-neutral-200 bg-white p-2 shadow-lg">
          {selected.length > 0 && (
            <button
              type="button"
              className="mb-1 w-full rounded px-2 py-1 text-left text-xs font-semibold text-primary hover:bg-primary/10"
              onMouseDown={(e) => { e.preventDefault(); onChange([]); }}
            >
              Clear selection
            </button>
          )}
          {options.length === 0 ? (
            <div className="px-2 py-1 text-xs text-neutral-400">No options</div>
          ) : (
            options.map((option) => (
              <label key={option} className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-sm hover:bg-neutral-50">
                <input
                  type="checkbox"
                  className="h-4 w-4"
                  checked={selected.includes(option)}
                  onMouseDown={(e) => { e.preventDefault(); toggle(option); }}
                  readOnly
                />
                <span className="truncate">{option}</span>
              </label>
            ))
          )}
        </div>
      )}
    </div>
  );
};

const InvoicesPage = () => {
  const { isAdmin } = usePermissions();
  const [invoices, setInvoices] = useState<SalesInvoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  // SAL-Edit-After-Issue: when true, the open edit form targets an already-issued
  // invoice and submits to the issued-details endpoint (stock/tax/totals reconciled).
  const [editingIssued, setEditingIssued] = useState(false);
  const [statusFilter, setStatusFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  // Enhancement 3 (FR-21/FR-22): multi-select Stockist & Sales Manager filters
  const [stockistFilter, setStockistFilter] = useState<string[]>([]);
  const [salesManagerFilter, setSalesManagerFilter] = useState<string[]>([]);
  // MCN-BUG-001: server-side pagination state
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<number | 'all'>(50);
  const [total, setTotal] = useState(0);
  const [customers, setCustomers] = useState<CustomerOption[]>([]);
  const [products, setProducts] = useState<ProductOption[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [selectedInvoice, setSelectedInvoice] = useState<SalesInvoice | null>(null);
  const [selectedInvoiceItems, setSelectedInvoiceItems] = useState<SalesInvoiceItem[]>([]);
  const [showInvoiceDetail, setShowInvoiceDetail] = useState(false);
  const [companyLocation, setCompanyLocation] = useState<CompanyLocation | null>(null);
  const [uomOptions, setUomOptions] = useState<UomOption[]>([]);
  const [batchOptionsByRow, setBatchOptionsByRow] = useState<Record<number, InvoiceBatchOption[]>>({});

  const [customerId, setCustomerId] = useState('');
  const [invoiceType, setInvoiceType] = useState<InvoiceTypeValue>('within_state');
  const [importExportCode, setImportExportCode] = useState('');
  const [invoiceDate, setInvoiceDate] = useState(todayLocalDateInputValue());
  const [dueDate, setDueDate] = useState('');
  const [isDueDateManuallyEdited, setIsDueDateManuallyEdited] = useState(false);
  const [notes, setNotes] = useState('');
  const [items, setItems] = useState<SalesLineItem[]>([]);
  // Enhancement 3: master lists + mandatory internal invoice fields
  const [stockists, setStockists] = useState<Stockist[]>([]);
  const [salesManagers, setSalesManagers] = useState<SalesManager[]>([]);
  const [stockistName, setStockistName] = useState('');
  const [stockistCity, setStockistCity] = useState('');
  const [salesManagerName, setSalesManagerName] = useState('');

  const isExportInvoice = invoiceType === 'export_invoice';
  const lineItemColumnCount = isExportInvoice ? 15 : 16;
  const lineItemTotalLabelColSpan = isExportInvoice ? 13 : 14;

  const invoiceTypeLabel = (value?: string) => {
    if (!value) return INVOICE_TYPE_LABELS.within_state;
    return INVOICE_TYPE_LABELS[value as InvoiceTypeValue] || INVOICE_TYPE_LABELS.within_state;
  };

  const gstColumnLabel = (type?: InvoiceTypeValue) => {
    if (type === 'other_states') return 'IGST %';
    if (type === 'union_territory') return 'GST % (CGST+UTGST)';
    return 'GST % (CGST+SGST)';
  };

  const deriveDefaultInvoiceType = useCallback((selectedCustomerId: string): InvoiceTypeValue => {
    const customer = customers.find((c) => c.id === selectedCustomerId);
    if (!customer) return 'within_state';

    if (!isIndiaCountry(customer.shipping_country || customer.billing_country)) {
      return 'export_invoice';
    }

    const customerStateCode = normalizeStateCodeToken(customer.shipping_state_code || customer.billing_state_code);
    const customerStateName = normalizeTextToken(customer.shipping_state || customer.billing_state);

    if (UNION_TERRITORY_CODES.has(customerStateCode) || UNION_TERRITORY_NAMES.has(customerStateName)) {
      return 'union_territory';
    }

    const companyStateCode = normalizeStateCodeToken(companyLocation?.state_code);
    const companyStateName = normalizeTextToken(companyLocation?.state);
    if (companyStateCode && customerStateCode) {
      if (companyStateCode !== customerStateCode) return 'other_states';
      return UNION_TERRITORY_CODES.has(customerStateCode) ? 'union_territory' : 'within_state';
    }
    if (companyStateName && customerStateName) {
      if (companyStateName !== customerStateName) return 'other_states';
      return UNION_TERRITORY_NAMES.has(customerStateName) ? 'union_territory' : 'within_state';
    }

    return 'other_states';
  }, [customers, companyLocation]);

  const selectedCustomer = customers.find((c) => c.id === customerId);
  const expectedInvoiceType = selectedCustomer
    ? deriveDefaultInvoiceType(selectedCustomer.id)
    : null;
  const allowedInvoiceTypeOptions = expectedInvoiceType
    ? INVOICE_TYPE_OPTIONS.filter((opt) => opt.value === expectedInvoiceType)
    : INVOICE_TYPE_OPTIONS;
  const isInvoiceTypeLocked = Boolean(expectedInvoiceType);

  const calculateInvoiceDueDate = useCallback((selectedCustomerId: string, selectedInvoiceDate: string) => {
    if (!selectedCustomerId || !selectedInvoiceDate) {
      return '';
    }

    const customer = customers.find((c) => c.id === selectedCustomerId);
    const paymentTermsDays = typeof customer?.payment_terms_days === 'number' && customer.payment_terms_days > 0
      ? customer.payment_terms_days
      : 0;

    return addDaysToDateInputValue(selectedInvoiceDate, paymentTermsDays);
  }, [customers]);

  // MCN-BUG-001: server-side paged/searched/filtered fetch. "All" loops through
  // every page so no record is truncated while still using the paginated API.
  const fetchInvoices = useCallback(async () => {
    const filters = {
      search: debouncedSearch || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      stockist: stockistFilter.length ? stockistFilter : undefined,
      sales_manager: salesManagerFilter.length ? salesManagerFilter : undefined,
    };
    try {
      setLoading(true);
      if (pageSize === 'all') {
        const collected: SalesInvoice[] = [];
        const chunk = 500;
        let current = 1;
        let fetchedTotal = 0;
        for (;;) {
          const res = await salesApi.listInvoices(statusFilter || undefined, current, chunk, filters);
          const batch = res.data.items || [];
          collected.push(...batch);
          fetchedTotal = res.data.total ?? collected.length;
          if (batch.length === 0 || collected.length >= fetchedTotal) break;
          current += 1;
        }
        setInvoices(collected);
        setTotal(fetchedTotal);
      } else {
        const res = await salesApi.listInvoices(statusFilter || undefined, page, pageSize, filters);
        setInvoices(res.data.items || []);
        setTotal(res.data.total ?? (res.data.items || []).length);
      }
    } catch {
      setError('Failed to load');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, page, pageSize, debouncedSearch, dateFrom, dateTo, stockistFilter, salesManagerFilter]);
  const fetchMasterData = async () => {
    try {
      const [c, p, comp, uom] = await Promise.all([
        apiClient.get('/api/v2/customers', { params: { page_size: 100 } }),
        apiClient.get('/api/v2/products', { params: { page_size: 100 } }),
        apiClient.get('/api/v2/company'),
        apiClient.get('/api/v2/products/uom'),
      ]);
      setCustomers(c.data.items || []);
      setProducts(p.data.items || []);
      setCompanyLocation({ state: comp.data?.state || '', state_code: comp.data?.state_code || '' });
      setUomOptions(uom.data || []);
    } catch {
      /* */
    }
  };
  // Enhancement 3: load active Stockist & Sales Manager masters for dropdowns/filters
  const fetchSalesMasters = async () => {
    try {
      const [st, sm] = await Promise.all([
        stockistsApi.list({ page_size: 1000 }),
        salesManagersApi.list({ page_size: 1000 }),
      ]);
      setStockists(st.items || []);
      setSalesManagers(sm.items || []);
    } catch {
      /* */
    }
  };

  useEffect(() => { fetchInvoices(); }, [fetchInvoices]);
  useEffect(() => { fetchMasterData(); fetchSalesMasters(); }, []);

  // MCN-BUG-001: debounce search box to avoid a request per keystroke
  useEffect(() => {
    const handle = setTimeout(() => setDebouncedSearch(searchQuery.trim()), 300);
    return () => clearTimeout(handle);
  }, [searchQuery]);

  // MCN-BUG-001: any filter/page-size change returns to the first page
  useEffect(() => { setPage(1); }, [statusFilter, debouncedSearch, dateFrom, dateTo, pageSize, stockistFilter, salesManagerFilter]);

  const resetForm = () => { setCustomerId(''); setInvoiceType('within_state'); setImportExportCode(''); setInvoiceDate(todayLocalDateInputValue()); setDueDate(''); setIsDueDateManuallyEdited(false); setNotes(''); setItems([]); setBatchOptionsByRow({}); setStockistName(''); setStockistCity(''); setSalesManagerName(''); setEditingId(null); setEditingIssued(false); setError(''); };

  // FR-18: Stockist City auto-fills from the selected Stockist (user may override).
  const handleStockistChange = (name: string) => {
    setStockistName(name);
    const match = stockists.find((s) => s.name === name);
    if (match && (match.city || '').trim()) {
      setStockistCity(match.city || '');
    }
  };
  const addItem = () => {
    setItems([
      ...items,
      {
        product_id: '',
        order_unit: '',
        batch_no: '',
        manufacture_date: '',
        expiry_date: '',
        quantity: 0,
        free_quantity: 0,
        unit_price: 0,
        discount_percent: 0,
        gst_rate: 18,
      },
    ]);
  };
  const paiseToRupees = (paise: number) => (Number.isFinite(paise) ? paise / 100 : 0);
  const rupeesToPaise = (value: string | number) => {
    const num = typeof value === 'number' ? value : parseFloat(value);
    return Number.isFinite(num) ? Math.round(num * 100) : 0;
  };

  // SAL-025: Auto-calculate due date from customer payment terms when customer changes
  const handleCustomerChange = (newCustomerId: string) => {
    setCustomerId(newCustomerId);
    setDueDate(calculateInvoiceDueDate(newCustomerId, invoiceDate));
    setIsDueDateManuallyEdited(false);
    setInvoiceType(deriveDefaultInvoiceType(newCustomerId));
  };

  useEffect(() => {
    if (!customerId) return;

    const customer = customers.find((c) => c.id === customerId);
    if (!customer) return;

    const expectedType = deriveDefaultInvoiceType(customerId);
    if (invoiceType !== expectedType) {
      setInvoiceType(expectedType);
    }
  }, [customerId, customers, deriveDefaultInvoiceType, invoiceType]);

  useEffect(() => {
    if (!customerId || !invoiceDate) {
      if (dueDate) {
        setDueDate('');
      }
      return;
    }

    // Wait until customer master is loaded to avoid transient blank due-date while editing.
    if (!customers.some((c) => c.id === customerId)) {
      return;
    }

    if (isDueDateManuallyEdited) {
      return;
    }

    const calculatedDueDate = calculateInvoiceDueDate(customerId, invoiceDate);
    if (calculatedDueDate !== dueDate) {
      setDueDate(calculatedDueDate);
    }
  }, [calculateInvoiceDueDate, customerId, invoiceDate, customers, dueDate, isDueDateManuallyEdited]);

  const updateItem = (idx: number, field: keyof SalesLineItem, value: string | number) => {
    const updated = [...items]; (updated[idx] as unknown as Record<string, unknown>)[field] = value;

    if (field === 'product_id') {
      const productId = String(value || '');
      const p = products.find(x => x.id === productId);
      if (p) {
        updated[idx].unit_price = p.mrp || p.selling_price;
        updated[idx].gst_rate = p.gst_rate;
        updated[idx].order_unit = resolvePackingUnit(p);
      } else {
        updated[idx].order_unit = '';
      }
      updated[idx].batch_no = '';
      updated[idx].manufacture_date = '';
      updated[idx].expiry_date = '';
      setItems(updated);
      setBatchOptionsByRow((prev) => ({ ...prev, [idx]: [] }));
      if (productId) {
        void loadBatchOptionsForRow(idx, productId, true);
      }
      return;
    }

    if (field === 'batch_no') {
      const selected = (batchOptionsByRow[idx] || []).find((opt) => opt.batch_no === String(value || ''));
      if (selected) {
        updated[idx].manufacture_date = selected.manufacture_date || '';
        updated[idx].expiry_date = selected.expiry_date || '';
      } else {
        updated[idx].manufacture_date = '';
        updated[idx].expiry_date = '';
      }
    }

    setItems(updated);
  };
  const removeItem = (idx: number) => {
    setItems(items.filter((_, i) => i !== idx));
    setBatchOptionsByRow((prev) => {
      const next: Record<number, InvoiceBatchOption[]> = {};
      Object.entries(prev).forEach(([rowKey, value]) => {
        const rowIndex = Number(rowKey);
        if (rowIndex < idx) next[rowIndex] = value;
        if (rowIndex > idx) next[rowIndex - 1] = value;
      });
      return next;
    });
  };
  const calcTotal = (i: SalesLineItem) => {
    const g = i.unit_price * i.quantity;
    const d = g * (i.discount_percent || 0) / 100;
    const t = g - d;
    const gstRate = isExportInvoice ? 0 : i.gst_rate;
    return Math.round(t + t * gstRate / 100);
  };
  const roundToNearestFivePaise = (value: number) => {
    if (!Number.isFinite(value)) return 0;
    const normalized = Math.round(value);
    const step = 500;
    if (normalized >= 0) return Math.floor(normalized / step) * step;
    return -Math.floor(Math.abs(normalized) / step) * step;
  };
  const formatAmount = (p: number) => `Rs. ${(p / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
  const deriveInvoicePaymentStatusLabel = (invoice?: Pick<SalesInvoice, 'status' | 'amount_paid' | 'total_amount'>) => {
    if (!invoice) return '-';
    const token = (invoice.status || '').trim().toLowerCase();
    if (token === 'draft') return 'Draft';
    if (token === 'cancelled') return 'Cancelled';
    if (token === 'returned') return 'Returned';

    const paid = Number(invoice.amount_paid || 0);
    const total = Number(invoice.total_amount || 0);

    if (paid <= 0) return 'Unpaid';
    if (total > 0 && paid >= total) return 'Fully Received';
    return 'Partially Received';
  };

  const invoiceStatusBadgeClass = (invoice?: Pick<SalesInvoice, 'status' | 'amount_paid' | 'total_amount'>) => {
    if (!invoice) return 'bg-gray-100 text-gray-700';
    const token = (invoice.status || '').trim().toLowerCase();
    if (token === 'draft') return 'bg-gray-100 text-gray-700';
    if (token === 'cancelled') return 'bg-red-100 text-red-700';
    if (token === 'returned') return 'bg-emerald-100 text-emerald-700';

    const paid = Number(invoice.amount_paid || 0);
    const total = Number(invoice.total_amount || 0);

    if (paid <= 0) return 'bg-blue-100 text-blue-700';
    if (total > 0 && paid >= total) return 'bg-green-100 text-green-700';
    return 'bg-amber-100 text-amber-700';
  };
  const productById = (id: string) => products.find(p => p.id === id);
  const uomAbbreviationById = useCallback((id?: string | null) => uomOptions.find((u) => u.id === id)?.abbreviation || '', [uomOptions]);
  const resolvePackingUnit = useCallback((product?: ProductOption) => {
    if (!product) return '';
    return uomAbbreviationById(product.alt_uom_id) || uomAbbreviationById(product.uom_id) || '';
  }, [uomAbbreviationById]);
  const resolveBaseUnit = useCallback((product?: ProductOption) => {
    if (!product) return '';
    const baseUnit = (product.sku || '').trim();
    if (baseUnit) return baseUnit;
    return uomAbbreviationById(product.uom_id) || '';
  }, [uomAbbreviationById]);

  const itemsTotalPaise = items.reduce((sum, item) => sum + calcTotal(item), 0);
  const roundedItemsTotalPaise = roundToNearestFivePaise(itemsTotalPaise);
  const roundOffPaise = roundedItemsTotalPaise - itemsTotalPaise;
  const viewExactTotalPaise = selectedInvoice
    ? Number(selectedInvoice.total_taxable_amount || 0) + Number(selectedInvoice.total_gst || 0)
    : 0;
  const viewRoundedTotalPaise = roundToNearestFivePaise(viewExactTotalPaise);
  const viewRoundOffPaise = viewRoundedTotalPaise - viewExactTotalPaise;
  const viewTotalLabelColSpan = selectedInvoice?.invoice_type === 'export_invoice' ? 4 : 5;
  const formatAvailableQty = (qty: number) => {
    if (!Number.isFinite(qty)) return '0';
    return Number(qty).toFixed(4).replace(/\.?0+$/, '');
  };
  const lineItemInputClass = 'h-9 w-full rounded border px-2 py-1.5 text-sm leading-5';
  const lineItemInputReadOnlyClass = 'h-9 w-full rounded border bg-neutral-50 px-2 py-1.5 text-sm text-neutral-700 leading-5';
  const lineItemSelectClass = 'h-9 w-full rounded border px-2 py-1.5 text-sm';
  const batchQtyErrorForRow = (rowIndex: number, item: SalesLineItem) => {
    const batchNo = (item.batch_no || '').trim();
    if (!batchNo || !item.product_id) return '';
    const options = batchOptionsByRow[rowIndex] || [];
    const selected = options.find((opt) => opt.batch_no === batchNo);
    if (!selected) return '';
    const requestedQty = items.reduce((sum, row) => {
      if (row.product_id !== item.product_id) return sum;
      if ((row.batch_no || '').trim() !== batchNo) return sum;
      return sum + Number(row.quantity || 0) + Number(row.free_quantity || 0);
    }, 0);
    if (requestedQty - Number(selected.available_qty || 0) > 1e-6) {
      return 'Entered quantity exceeds available stock in selected batch';
    }
    return '';
  };
  const batchQtyErrorSummary = useMemo(() => {
    for (let idx = 0; idx < items.length; idx += 1) {
      const item = items[idx];
      const batchNo = (item.batch_no || '').trim();
      if (!batchNo || !item.product_id) continue;
      const options = batchOptionsByRow[idx] || [];
      const selected = options.find((opt) => opt.batch_no === batchNo);
      if (!selected) continue;
      const requestedQty = items.reduce((sum, row) => {
        if (row.product_id !== item.product_id) return sum;
        if ((row.batch_no || '').trim() !== batchNo) return sum;
        return sum + Number(row.quantity || 0) + Number(row.free_quantity || 0);
      }, 0);
      if (requestedQty - Number(selected.available_qty || 0) > 1e-6) {
        return `Line item ${idx + 1}: Entered quantity exceeds available stock in selected batch`;
      }
    }
    return '';
  }, [batchOptionsByRow, items]);

  const loadBatchOptionsForRow = useCallback(async (rowIndex: number, productId: string, autoSelectSingle: boolean) => {
    try {
      const response = await salesApi.getInvoiceBatchOptions(productId);
      const options = response.data.items || [];
      setBatchOptionsByRow((prev) => ({ ...prev, [rowIndex]: options }));

      setItems((prev) => {
        if (rowIndex < 0 || rowIndex >= prev.length) return prev;
        const currentRow = prev[rowIndex];
        if (currentRow.product_id !== productId) return prev;

        const next = [...prev];
        const updatedRow = { ...currentRow };
        const product = products.find((p) => p.id === productId);
        if (product) {
          updatedRow.order_unit = resolvePackingUnit(product);
        }

        if (options.length === 1 && autoSelectSingle) {
          const selected = options[0];
          updatedRow.batch_no = selected.batch_no;
          updatedRow.manufacture_date = selected.manufacture_date || '';
          updatedRow.expiry_date = selected.expiry_date || '';
        } else if (updatedRow.batch_no) {
          const selected = options.find((opt) => opt.batch_no === updatedRow.batch_no);
          if (selected) {
            updatedRow.manufacture_date = selected.manufacture_date || '';
            updatedRow.expiry_date = selected.expiry_date || '';
          } else {
            updatedRow.batch_no = '';
            updatedRow.manufacture_date = '';
            updatedRow.expiry_date = '';
          }
        }

        next[rowIndex] = updatedRow;
        return next;
      });
    } catch {
      setBatchOptionsByRow((prev) => ({ ...prev, [rowIndex]: [] }));
    }
  }, [products, resolvePackingUnit]);

  useEffect(() => {
    if (!showForm) return;
    items.forEach((item, idx) => {
      if (!item.product_id) return;
      if (batchOptionsByRow[idx] !== undefined) return;
      void loadBatchOptionsForRow(idx, item.product_id, false);
    });
  }, [showForm, items, batchOptionsByRow, loadBatchOptionsForRow]);

  const handleDateFromChange = (value: string) => {
    setDateFrom(value);
    if (dateTo && value && value > dateTo) {
      setDateTo(value);
    }
  };

  const handleDateToChange = (value: string) => {
    setDateTo(value);
    if (dateFrom && value && value < dateFrom) {
      setDateFrom(value);
    }
  };

  const handleSubmit = async () => {
    if (!customerId || items.length === 0) { setError('Select customer & add items'); return; }

    // FR-19: Stockist Name, Stockist City and Sales Manager Name are mandatory.
    if (!stockistName.trim()) { setError('Stockist Name is required'); return; }
    if (!stockistCity.trim()) { setError('Stockist City is required'); return; }
    if (!salesManagerName.trim()) { setError('Sales Manager Name is required'); return; }

    const todayIso = todayLocalDateInputValue();
    const invalidMfgDateIndex = items.findIndex(
      (i) => i.manufacture_date && i.manufacture_date >= todayIso,
    );
    if (invalidMfgDateIndex >= 0) {
      setError(`Line item ${invalidMfgDateIndex + 1}: MFG date must be a past date`);
      return;
    }

    const invalidExpDateIndex = items.findIndex(
      (i) => i.expiry_date && i.expiry_date <= todayIso,
    );
    if (invalidExpDateIndex >= 0) {
      setError(`Line item ${invalidExpDateIndex + 1}: EXP date must be a future date`);
      return;
    }

    const invalidDateOrderIndex = items.findIndex(
      (i) => i.manufacture_date && i.expiry_date && i.expiry_date <= i.manufacture_date,
    );
    if (invalidDateOrderIndex >= 0) {
      setError(`Line item ${invalidDateOrderIndex + 1}: EXP date must be later than MFG date`);
      return;
    }

    if (batchQtyErrorSummary) {
      setError(batchQtyErrorSummary);
      return;
    }

    setSubmitting(true); setError('');
    try {
      const payload: CreateInvoicePayload = {
        customer_id: customerId, invoice_date: invoiceDate,
        due_date: dueDate || undefined,
        bill_to_customer_id: customerId,
        invoice_type: invoiceType,
        import_export_code: importExportCode.trim() || undefined,
        stockist_name: stockistName.trim(),
        stockist_city: stockistCity.trim(),
        sales_manager_name: salesManagerName.trim(),
        notes: notes || undefined,
        items: items.map(i => ({
          product_id: i.product_id,
          order_unit: i.order_unit || undefined,
          batch_no: i.batch_no || undefined,
          manufacture_date: i.manufacture_date || undefined,
          expiry_date: i.expiry_date || undefined,
          quantity: Number(i.quantity),
          free_quantity: Number(i.free_quantity || 0),
          unit_price: Number(i.unit_price),
          discount_percent: Number(i.discount_percent || 0),
          gst_rate: Number(isExportInvoice ? 0 : i.gst_rate),
        })),
      };
      if (editingId && editingIssued) {
        await salesApi.updateIssuedInvoice(editingId, payload, { suppressGlobalErrorToast: true });
      } else if (editingId) {
        await salesApi.updateInvoice(editingId, payload, { suppressGlobalErrorToast: true });
      } else {
        await salesApi.createInvoice(payload, { suppressGlobalErrorToast: true });
      }
      setShowForm(false); resetForm(); fetchInvoices();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      const messages = extractApiMessages(detail);
      const popupMessages = messages.length > 0 ? messages : ['Failed to save invoice'];
      popupMessages.forEach((message) => toast.error(message));
      setError(popupMessages.join('\n'));
    } finally { setSubmitting(false); }
  };

  const handleIssue = async (id: string) => {
    const confirmed = await confirmWithToast('Issue this invoice? This will deduct stock.', {
      type: 'warning',
    });
    if (!confirmed) return;
    try { await salesApi.issueInvoice(id, { suppressGlobalErrorToast: true }); fetchInvoices(); }
    catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      const messages = extractApiMessages(detail);
      if (messages.length === 0) {
        toast.error('Issue failed');
      } else {
        messages.forEach((message) => toast.error(message));
      }
    }
  };

  const handleDownloadPDF = async (inv: SalesInvoice) => {
    try {
      toast.info('Generating PDF...');
      const response = await salesApi.downloadInvoicePdf(inv.id);
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `Invoice-${inv.invoice_number}.pdf`);
      document.body.appendChild(link);
      link.click();
      window.URL.revokeObjectURL(url);
      link.remove();
      toast.success('PDF downloaded successfully');
    } catch {
      toast.error('Failed to download PDF');
    }
  };

  // FR-24: Export the Sales Invoice list reflecting the ACTIVE filters
  // (status, search, date range, Stockist, Sales Manager). BOM-prefixed for Excel.
  const handleExportCsv = async () => {
    try {
      toast.info('Preparing export...');
      const filters = {
        search: debouncedSearch || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        stockist: stockistFilter.length ? stockistFilter : undefined,
        sales_manager: salesManagerFilter.length ? salesManagerFilter : undefined,
      };
      const collected: SalesInvoice[] = [];
      const chunk = 500;
      let current = 1;
      let fetchedTotal = 0;
      for (;;) {
        const res = await salesApi.listInvoices(statusFilter || undefined, current, chunk, filters);
        const batch = res.data.items || [];
        collected.push(...batch);
        fetchedTotal = res.data.total ?? collected.length;
        if (batch.length === 0 || collected.length >= fetchedTotal) break;
        current += 1;
      }

      const headers = [
        'Invoice Number', 'Customer', 'Invoice Type', 'Invoice Date', 'Due Date',
        'Stockist', 'Stockist City', 'Sales Manager', 'Status', 'Total (Rs.)', 'Amount Due (Rs.)',
      ];
      const escape = (value: unknown) => {
        const text = value === null || value === undefined ? '' : String(value);
        return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
      };
      const rupees = (paise: number) => (Number(paise || 0) / 100).toFixed(2);
      const rows = collected.map((inv) => [
        inv.invoice_number,
        customerNameById(inv.customer_id),
        invoiceTypeLabel(inv.invoice_type),
        inv.invoice_date,
        inv.due_date || '',
        inv.stockist_name || '',
        inv.stockist_city || '',
        inv.sales_manager_name || '',
        deriveInvoicePaymentStatusLabel(inv),
        rupees(inv.total_amount),
        rupees(inv.amount_due),
      ].map(escape).join(','));

      const csv = `﻿${[headers.join(','), ...rows].join('\n')}`;
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `sales-invoices-${todayLocalDateInputValue()}.csv`);
      document.body.appendChild(link);
      link.click();
      window.URL.revokeObjectURL(url);
      link.remove();
      toast.success(`Exported ${collected.length} invoice(s)`);
    } catch {
      toast.error('Failed to export invoices');
    }
  };

  const handleViewInvoice = async (inv: SalesInvoice) => {
    try {
      const { data } = await salesApi.getInvoice(inv.id);
      setSelectedInvoice(data.invoice || inv);
      setSelectedInvoiceItems(data.items || []);
      setShowInvoiceDetail(true);
    } catch {
      setSelectedInvoice(inv);
      setSelectedInvoiceItems([]);
      setShowInvoiceDetail(true);
    }
  };

  // SAL-027 / SAL-Edit-After-Issue: load the selected invoice into the edit form.
  // `issued` routes the save to the reconciling issued-details endpoint.
  const loadInvoiceIntoEditForm = (issued: boolean) => {
    if (!selectedInvoice) return;
    setShowInvoiceDetail(false);
    setEditingId(selectedInvoice.id);
    setEditingIssued(issued);
    setCustomerId(selectedInvoice.customer_id);
    setInvoiceType((selectedInvoice.invoice_type as InvoiceTypeValue) || deriveDefaultInvoiceType(selectedInvoice.customer_id));
    setImportExportCode(selectedInvoice.import_export_code || '');
    setInvoiceDate(selectedInvoice.invoice_date);
    setDueDate(selectedInvoice.due_date || '');
    setIsDueDateManuallyEdited(true);
    setNotes(selectedInvoice.notes || '');
    setStockistName(selectedInvoice.stockist_name || '');
    setStockistCity(selectedInvoice.stockist_city || '');
    setSalesManagerName(selectedInvoice.sales_manager_name || '');
    setItems(selectedInvoiceItems.map(i => ({
      product_id: i.product_id,
      order_unit: i.order_unit || '',
      batch_no: i.batch_no || '',
      manufacture_date: i.manufacture_date || '',
      expiry_date: i.expiry_date || '',
      quantity: i.quantity,
      free_quantity: i.free_quantity || 0,
      unit_price: i.unit_price,
      discount_percent: i.discount_percent || 0,
      gst_rate: i.gst_rate,
    })));
    setShowForm(true);
  };

  const customerNameById = (customerId: string) => {
    return customers.find((c) => c.id === customerId)?.company_name || 'Unknown customer';
  };
  const productNameById = (productId: string) => {
    return products.find((p) => p.id === productId)?.name || productId;
  };

  // MCN-BUG-001: filtering/searching now happens server-side; derive paging summary
  const totalPages = pageSize === 'all' ? 1 : Math.max(1, Math.ceil(total / pageSize));
  const rangeStart = total === 0 ? 0 : pageSize === 'all' ? 1 : (page - 1) * pageSize + 1;
  const rangeEnd = pageSize === 'all' ? total : Math.min(page * pageSize, total);

  return (
    <AppLayout title="Sales Invoices">
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <select className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
              <option value="">All</option><option value="draft">Draft</option><option value="issued">Issued</option><option value="partial_paid">Partial Paid</option><option value="paid">Paid</option><option value="returned">Returned</option><option value="cancelled">Cancelled</option>
            </select>
            <input
              type="text"
              className="w-64 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm"
              placeholder="Search invoice #, customer, status..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <div className="inline-flex items-center gap-2 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm">
              <span className="text-xs font-semibold uppercase tracking-wide text-neutral-500">From</span>
              <input
                type="date"
                className="bg-transparent text-sm outline-none"
                value={dateFrom}
                max={dateTo || undefined}
                onChange={(e) => handleDateFromChange(e.target.value)}
                title="Invoice date from"
              />
            </div>
            <div className="inline-flex items-center gap-2 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm">
              <span className="text-xs font-semibold uppercase tracking-wide text-neutral-500">To</span>
              <input
                type="date"
                className="bg-transparent text-sm outline-none"
                value={dateTo}
                min={dateFrom || undefined}
                onChange={(e) => handleDateToChange(e.target.value)}
                title="Invoice date to"
              />
            </div>
            {/* Enhancement 3 (FR-21/FR-22): Stockist & Sales Manager multi-select filters */}
            <MultiSelectFilter
              label="Stockist"
              options={stockists.map((s) => s.name)}
              selected={stockistFilter}
              onChange={setStockistFilter}
            />
            <MultiSelectFilter
              label="Sales Manager"
              options={salesManagers.map((s) => s.name)}
              selected={salesManagerFilter}
              onChange={setSalesManagerFilter}
            />
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleExportCsv}
              className="inline-flex items-center gap-1 rounded-lg border border-neutral-200 bg-white px-4 py-2.5 text-sm font-semibold text-neutral-700 hover:bg-neutral-50"
              title="Export the filtered Sales Invoice list to CSV"
            >
              <span className="material-icons text-sm" aria-hidden="true">download</span>
              Export CSV
            </button>
            <button onClick={() => { resetForm(); setShowForm(true); }} className="rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-primary/20 hover:bg-primary/90">+ New Invoice</button>
          </div>
        </div>

        <div className="hms-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-neutral-200 bg-neutral-50">
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Invoice Number</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Customer</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Invoice Type</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Date</th>
                <th className="px-4 py-3 text-left font-semibold text-neutral-600">Due Date</th>
                <th className="px-4 py-3 text-right font-semibold text-neutral-600">Amount</th>
                <th className="px-4 py-3 text-right font-semibold text-neutral-600">Due</th>
                <th className="px-4 py-3 text-center font-semibold text-neutral-600">Status</th>
                <th className="px-4 py-3 text-center font-semibold text-neutral-600">Actions</th>
              </tr></thead>
              <tbody>
                {loading ? <tr><td colSpan={9} className="px-4 py-8 text-center text-neutral-500">Loading...</td></tr>
                : invoices.length === 0 ? <tr><td colSpan={9} className="px-4 py-8 text-center text-neutral-500">No invoices</td></tr>
                : invoices.map(inv => (
                  <tr key={inv.id} className="border-b border-neutral-100 hover:bg-neutral-50">
                    <td className="px-4 py-3 font-medium">{inv.invoice_number}</td>
                    <td className="px-4 py-3">{customerNameById(inv.customer_id)}</td>
                    <td className="px-4 py-3">{invoiceTypeLabel(inv.invoice_type)}</td>
                    <td className="px-4 py-3">{inv.invoice_date}</td>
                    <td className="px-4 py-3">{inv.due_date || '-'}</td>
                    <td className="px-4 py-3 text-right font-medium">{formatAmount(inv.total_amount)}</td>
                    <td className="px-4 py-3 text-right font-medium text-red-600">{inv.amount_due > 0 ? formatAmount(inv.amount_due) : '-'}</td>
                    <td className="px-4 py-3 text-center"><span className={`inline-block rounded-full px-2.5 py-1 text-xs font-semibold ${invoiceStatusBadgeClass(inv)}`}>{deriveInvoicePaymentStatusLabel(inv)}</span></td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex items-center justify-center gap-2">
                        <button onClick={() => handleViewInvoice(inv)} className="rounded px-2 py-1 text-xs font-medium text-primary hover:bg-primary/10">View</button>
                        {isAdmin && inv.status === 'draft' && <button onClick={() => handleIssue(inv.id)} className="rounded px-2 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50">Issue</button>}
                        <button
                          onClick={() => handleDownloadPDF(inv)}
                          className="inline-flex items-center gap-1 rounded border border-neutral-200 bg-white px-2.5 py-1 text-xs font-semibold text-neutral-700 hover:bg-neutral-50"
                          title="Download PDF"
                        >
                          <span className="material-icons text-sm" aria-hidden="true">picture_as_pdf</span>
                          Download PDF
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* MCN-BUG-001: pagination controls — rows-per-page selector + Prev/Next + page indicator */}
          {!loading && (
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-neutral-200 px-4 py-3 text-xs text-neutral-600">
              <div className="flex items-center gap-2">
                <span className="font-medium">Rows per page</span>
                <select
                  className="rounded border border-neutral-200 bg-white px-2 py-1 text-xs"
                  value={pageSize === 'all' ? 'all' : String(pageSize)}
                  onChange={(e) => setPageSize(e.target.value === 'all' ? 'all' : Number(e.target.value))}
                >
                  <option value="20">20</option>
                  <option value="50">50</option>
                  <option value="100">100</option>
                  <option value="all">All</option>
                </select>
                <span className="text-neutral-500">
                  {total === 0 ? 'No invoices' : `Showing ${rangeStart}-${rangeEnd} of ${total}`}
                </span>
              </div>
              {pageSize !== 'all' && (
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page <= 1}
                    className="rounded border border-neutral-200 bg-white px-3 py-1 font-semibold text-neutral-700 disabled:cursor-not-allowed disabled:opacity-40 hover:bg-neutral-50"
                  >
                    Previous
                  </button>
                  <span className="font-medium">Page {page} of {totalPages}</span>
                  <button
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    disabled={page >= totalPages}
                    className="rounded border border-neutral-200 bg-white px-3 py-1 font-semibold text-neutral-700 disabled:cursor-not-allowed disabled:opacity-40 hover:bg-neutral-50"
                  >
                    Next
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {showForm && createPortal(
          <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-2 sm:p-4 backdrop-blur-sm">
            <div className="hms-card my-4 sm:my-8 w-[min(96vw,1500px)] max-w-none space-y-6 p-4 sm:p-6">
              <h2 className="font-display text-xl font-bold">{editingId ? 'Modify/Change' : 'New'} Invoice</h2>
              {batchQtyErrorSummary && batchQtyErrorSummary !== error && (
                <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                  {batchQtyErrorSummary}
                </div>
              )}
              {error && <div className="rounded-lg bg-red-50 p-3 text-sm text-red-600">{error}</div>}
              
              {!editingId && (
                <div className="rounded-lg border border-neutral-200 bg-neutral-50 p-4 text-sm text-neutral-600">
                  Invoice creation is independent of Sales Order auto-fill.
                </div>
              )}

              <div className="grid grid-cols-1 gap-4 md:grid-cols-5">
                {/* SAL-025: Customer select triggers due date auto-calc */}
                <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Customer *</label><select className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={customerId} onChange={e => handleCustomerChange(e.target.value)}><option value="">Select</option>{customers.map(c => <option key={c.id} value={c.id}>{c.company_name} ({c.customer_code})</option>)}</select></div>
                <div>
                  <label className="mb-1 block text-sm font-semibold text-neutral-700">Invoice Type *</label>
                  <select
                    className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm disabled:bg-neutral-100 disabled:text-neutral-600"
                    value={invoiceType}
                    onChange={e => setInvoiceType(e.target.value as InvoiceTypeValue)}
                    disabled={!customerId || isInvoiceTypeLocked}
                  >
                    {allowedInvoiceTypeOptions.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                  </select>
                  {isInvoiceTypeLocked && (
                    <p className="mt-1 text-xs text-neutral-500">Auto-selected from customer shipping location.</p>
                  )}
                  {!isExportInvoice && <p className="mt-1 text-xs text-neutral-500">Applied Tax Type: {gstColumnLabel(invoiceType).replace(' %', '')}</p>}
                </div>
                <div>
                  <label className="mb-1 block text-sm font-semibold text-neutral-700">Import &amp; Export Code</label>
                  <input type="text" className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={importExportCode} onChange={e => setImportExportCode(e.target.value)} placeholder="Optional" />
                </div>
                <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Invoice Date *</label><input type="date" className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" value={invoiceDate} onChange={e => setInvoiceDate(e.target.value)} /></div>
                {/* SAL-029: Due Date is fully auto-calculated for invoices */}
                <div>
                  <label className="mb-1 block text-sm font-semibold text-neutral-700">Due Date <span className="text-xs text-neutral-400">(auto default, editable)</span></label>
                  <input
                    type="date"
                    className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm"
                    value={dueDate}
                    onChange={e => {
                      setDueDate(e.target.value);
                      setIsDueDateManuallyEdited(true);
                    }}
                  />
                </div>
              </div>
              {/* Enhancement 3: mandatory internal fields (not printed on the PDF) */}
              <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                <div>
                  <label className="mb-1 block text-sm font-semibold text-neutral-700">Stockist Name *</label>
                  <SearchableSelect
                    value={stockistName}
                    options={stockists.map((s) => s.name)}
                    placeholder="Search stockist..."
                    onChange={handleStockistChange}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-semibold text-neutral-700">Stockist City *</label>
                  <input
                    type="text"
                    className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm"
                    value={stockistCity}
                    onChange={(e) => setStockistCity(e.target.value)}
                    placeholder="Auto-fills from stockist (editable)"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-semibold text-neutral-700">Sales Manager Name *</label>
                  <SearchableSelect
                    value={salesManagerName}
                    options={salesManagers.map((s) => s.name)}
                    placeholder="Search sales manager..."
                    onChange={setSalesManagerName}
                  />
                </div>
                <p className="text-xs text-neutral-400 md:col-span-3">These are internal operational fields and are not shown on the printed/PDF invoice.</p>
              </div>
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="text-sm font-semibold">Items</h3>
                  <div className="flex items-center gap-2">
                    {isExportInvoice && (
                      <button onClick={addItem} className="rounded border border-neutral-200 bg-white px-3 py-1.5 text-xs font-semibold text-neutral-700 hover:bg-neutral-50">
                        + Add Cost
                      </button>
                    )}
                    <button onClick={addItem} className="rounded bg-primary/10 px-3 py-1.5 text-xs font-semibold text-primary">
                      + Add Item
                    </button>
                  </div>
                </div>
                <div className="overflow-x-auto rounded-lg border border-neutral-200">
                  <table className="w-full min-w-[2100px] table-fixed text-sm">
                    <thead>
                      <tr className="bg-neutral-50">
                        <th className="w-[18%] px-3 py-2 text-left">Product</th>
                        <th className="w-[8%] px-3 py-2 text-left">Product Code</th>
                        <th className="w-[10%] px-3 py-2 text-left">Description</th>
                        <th className="w-[8%] px-3 py-2 text-left">Packing Unit</th>
                        <th className="w-[8%] px-3 py-2 text-left">Base Unit</th>
                        <th className="w-[12%] px-3 py-2 text-left">Batch</th>
                        <th className="w-[12%] px-3 py-2 text-left">MFG Date</th>
                        <th className="w-[12%] px-3 py-2 text-left">EXP Date</th>
                        <th className="w-[5%] px-3 py-2 text-left">HSN</th>
                        <th className="w-16 px-3 py-2 text-right">Qty</th>
                        <th className="w-16 px-3 py-2 text-right">Free</th>
                        <th className="w-28 px-3 py-2 text-right">MRP (Rs.)</th>
                        <th className="w-16 px-3 py-2 text-right">Disc %</th>
                        {!isExportInvoice && <th className="w-28 px-3 py-2 text-right">{gstColumnLabel(invoiceType)}</th>}
                        <th className="w-28 px-3 py-2 text-right">Total</th>
                        <th className="w-20 px-3 py-2 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((item, idx) => {
                        const prod = productById(item.product_id);
                        const rowBatchOptions = batchOptionsByRow[idx] || [];
                        const hasMultipleBatches = rowBatchOptions.length > 1;
                        const hasSingleBatch = rowBatchOptions.length === 1;
                        const batchQtyError = batchQtyErrorForRow(idx, item);
                        return (
                        <tr key={idx} className="border-t border-neutral-100">
                          <td className="px-3 py-2">
                            <select className={lineItemSelectClass} value={item.product_id} onChange={e => updateItem(idx, 'product_id', e.target.value)}>
                              <option value="">Select</option>
                              {products.map(p => <option key={p.id} value={p.id}>{p.name} ({p.product_code})</option>)}
                            </select>
                          </td>
                          {/* SAL-013: Product Code column */}
                          <td className="px-3 py-2 text-xs text-neutral-500 font-mono">{prod?.product_code || '-'}</td>
                          {/* SAL-014: Description column */}
                          <td className="px-3 py-2 text-xs text-neutral-500">{prod?.description || prod?.name || '-'}</td>
                          <td className="px-3 py-2">
                            <input type="text" className={lineItemInputReadOnlyClass} value={item.order_unit || ''} readOnly placeholder="Auto from product" />
                          </td>
                          <td className="px-3 py-2">
                            <input type="text" className={lineItemInputReadOnlyClass} value={resolveBaseUnit(prod)} readOnly placeholder="Auto from product" />
                          </td>
                          <td className="px-3 py-2">
                            {hasMultipleBatches ? (
                              <select
                                className={lineItemSelectClass}
                                value={item.batch_no || ''}
                                onChange={e => updateItem(idx, 'batch_no', e.target.value)}
                              >
                                <option value="">Select batch</option>
                                {rowBatchOptions.map((opt) => (
                                  <option key={opt.batch_no} value={opt.batch_no}>
                                    {opt.batch_no} (Avail: {formatAvailableQty(opt.available_qty)})
                                  </option>
                                ))}
                              </select>
                            ) : (
                              <input
                                type="text"
                                className={lineItemInputReadOnlyClass}
                                value={hasSingleBatch ? (item.batch_no || rowBatchOptions[0].batch_no) : ''}
                                readOnly
                                placeholder={item.product_id ? 'No batch available' : 'Select product first'}
                              />
                            )}
                          </td>
                          <td className="px-3 py-2">
                            <input type="date" className={lineItemInputReadOnlyClass} value={item.manufacture_date || ''} readOnly />
                          </td>
                          <td className="px-3 py-2">
                            <input type="date" className={lineItemInputReadOnlyClass} value={item.expiry_date || ''} readOnly />
                          </td>
                          {/* SAL-021: HSN Code column */}
                          <td className="px-3 py-2 text-xs text-neutral-500">{prod?.hsn_code || '-'}</td>
                          <td className="px-3 py-2">
                            <input
                              type="number"
                              min="0.01"
                              step="0.01"
                              className={`${lineItemInputClass} text-right ${batchQtyError ? 'border-red-300' : ''}`}
                              value={emptyWhenZero(item.quantity)}
                              onChange={e => updateItem(idx, 'quantity', parseFloat(e.target.value) || 0)}
                              placeholder="Qty"
                            />
                          </td>
                          <td className="px-3 py-2">
                            <input type="number" min="0" step="0.01" className={`${lineItemInputClass} text-right`} value={emptyWhenZero(item.free_quantity)} onChange={e => updateItem(idx, 'free_quantity', parseFloat(e.target.value) || 0)} />
                          </td>
                          {/* SAL-020: MRP auto-fills from Product Master */}
                          <td className="px-3 py-2">
                            <input type="number" min="0" step="0.01" className={`${lineItemInputClass} text-right`} value={item.unit_price ? paiseToRupees(item.unit_price) : ''} onChange={e => updateItem(idx, 'unit_price', rupeesToPaise(e.target.value))} />
                          </td>
                          <td className="px-3 py-2">
                            <input type="number" min="0" max="100" className={`${lineItemInputClass} text-right`} value={emptyWhenZero(item.discount_percent)} onChange={e => updateItem(idx, 'discount_percent', parseFloat(e.target.value) || 0)} />
                          </td>
                          {!isExportInvoice && (
                            <td className="px-3 py-2">
                              <select className={`${lineItemSelectClass} min-w-[70px] border-neutral-300 bg-white text-neutral-900 appearance-auto`} value={item.gst_rate} onChange={e => updateItem(idx, 'gst_rate', parseInt(e.target.value))}>
                                <option value={0}>0%</option>
                                <option value={5}>5%</option>
                                <option value={12}>12%</option>
                                <option value={18}>18%</option>
                                <option value={28}>28%</option>
                              </select>
                            </td>
                          )}
                          <td className="px-3 py-2 text-right font-medium">{formatAmount(calcTotal(item))}</td>
                          <td className="px-3 py-2 text-right">
                            <button onClick={() => removeItem(idx)} className="inline-flex items-center gap-1 whitespace-nowrap text-red-500">
                              <span className="material-icons text-sm" aria-hidden="true">delete_outline</span>Remove
                            </button>
                          </td>
                        </tr>
                        );
                      })}
                  {items.length === 0 && <tr><td colSpan={lineItemColumnCount} className="px-3 py-4 text-center text-neutral-400">No items</td></tr>}
                    </tbody>
                    {items.length > 0 && (
                      <tfoot>
                        <tr className="border-t-2 bg-neutral-50">
                          <td colSpan={lineItemTotalLabelColSpan} className="px-3 py-2 text-right font-semibold">Total:</td>
                          <td className="px-3 py-2 text-right font-medium">{formatAmount(itemsTotalPaise)}</td>
                          <td></td>
                        </tr>
                        {roundOffPaise !== 0 && (
                          <tr className="bg-neutral-50">
                            <td colSpan={lineItemTotalLabelColSpan} className="px-3 py-2 text-right font-semibold">Round Off:</td>
                            <td className="px-3 py-2 text-right font-medium">{formatAmount(roundOffPaise)}</td>
                            <td></td>
                          </tr>
                        )}
                        <tr className="bg-neutral-50">
                          <td colSpan={lineItemTotalLabelColSpan} className="px-3 py-2 text-right font-semibold">Grand Total:</td>
                          <td className="px-3 py-2 text-right font-bold text-primary">{formatAmount(roundedItemsTotalPaise)}</td>
                          <td></td>
                        </tr>
                      </tfoot>
                    )}
                  </table>
                </div>
              </div>
              <div><label className="mb-1 block text-sm font-semibold text-neutral-700">Notes</label><textarea className="w-full rounded-lg border border-neutral-200 px-3 py-2 text-sm" rows={2} value={notes} onChange={e => setNotes(e.target.value)} /></div>
              <div className="flex justify-end gap-3">
                <button onClick={() => { setShowForm(false); resetForm(); }} className="rounded-lg border border-neutral-200 bg-white px-4 py-2.5 text-sm font-semibold text-neutral-600">Cancel</button>
                <button onClick={handleSubmit} disabled={submitting} className="rounded-lg bg-primary px-6 py-2.5 text-sm font-semibold text-white shadow-lg shadow-primary/20 disabled:opacity-50">{submitting ? 'Saving...' : editingId ? 'Update' : 'Create Invoice'}</button>
              </div>
            </div>
          </div>,
          document.body
        )}

        {showInvoiceDetail && selectedInvoice && createPortal(
          <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4 backdrop-blur-sm" onClick={() => setShowInvoiceDetail(false)}>
            <div className="hms-card my-8 w-full max-w-3xl space-y-6 p-6" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="font-display text-xl font-bold">Invoice: {selectedInvoice.invoice_number}</h2>
                  <p className="mt-1 text-sm text-neutral-600">Customer: {customers.find(c => c.id === selectedInvoice.customer_id)?.company_name || '-'}</p>
                </div>
                <div className="flex items-center gap-2">
                  {/* SAL-027: Edit button in Invoice View for draft invoices */}
                  {selectedInvoice.status === 'draft' && (
                    <button
                      onClick={() => loadInvoiceIntoEditForm(false)}
                      className="inline-flex items-center gap-1 rounded-lg border border-primary bg-primary/5 px-3 py-2 text-xs font-semibold text-primary hover:bg-primary/10"
                    >
                      <span className="material-icons text-sm" aria-hidden="true">edit</span>
                      Edit Invoice
                    </button>
                  )}
                  {/* SAL-Edit-After-Issue: authorized users may edit an issued invoice with
                      no allocated receipts; stock/tax/totals are reconciled server-side. */}
                  {isAdmin && selectedInvoice.status === 'issued' && selectedInvoice.amount_paid === 0 && (
                    <button
                      onClick={() => loadInvoiceIntoEditForm(true)}
                      className="inline-flex items-center gap-1 rounded-lg border border-amber-500 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-700 hover:bg-amber-100"
                      title="Edit issued invoice (stock, tax and totals will be recalculated)"
                    >
                      <span className="material-icons text-sm" aria-hidden="true">edit</span>
                      Edit Issued Invoice
                    </button>
                  )}
                  <button
                    onClick={() => handleDownloadPDF(selectedInvoice)}
                    className="inline-flex items-center gap-1 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs font-semibold text-neutral-700 hover:bg-neutral-50"
                  >
                    <span className="material-icons text-sm" aria-hidden="true">picture_as_pdf</span>
                    Download PDF
                  </button>
                  <button onClick={() => setShowInvoiceDetail(false)} className="text-2xl text-neutral-400 hover:text-neutral-600">X</button>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 rounded-lg bg-neutral-50 p-4 md:grid-cols-5">
                <div>
                  <p className="text-xs text-neutral-600">Invoice Date</p>
                  <p className="font-medium">{selectedInvoice.invoice_date}</p>
                </div>
                <div>
                  <p className="text-xs text-neutral-600">Due Date</p>
                  <p className="font-medium">{selectedInvoice.due_date || '-'}</p>
                </div>
                <div>
                  <p className="text-xs text-neutral-600">Invoice Type</p>
                  <p className="font-medium">{invoiceTypeLabel(selectedInvoice.invoice_type)}</p>
                </div>
                <div>
                  <p className="text-xs text-neutral-600">Status</p>
                  <span className={`inline-block rounded-full px-2.5 py-1 text-xs font-semibold ${invoiceStatusBadgeClass(selectedInvoice)}`}>
                    {deriveInvoicePaymentStatusLabel(selectedInvoice)}
                  </span>
                </div>
                <div>
                  <p className="text-xs text-neutral-600">Total</p>
                  <p className="font-semibold">{formatAmount(selectedInvoice.total_amount)}</p>
                </div>
              </div>

              {selectedInvoice.import_export_code && (
                <div className="rounded-lg border border-neutral-200 p-3">
                  <p className="text-xs text-neutral-600">Import &amp; Export Code</p>
                  <p className="font-medium text-neutral-800">{selectedInvoice.import_export_code}</p>
                </div>
              )}

              {/* Enhancement 3: internal operational fields (not on the PDF invoice) */}
              <div className="grid grid-cols-1 gap-4 rounded-lg border border-neutral-200 p-4 md:grid-cols-3">
                <div>
                  <p className="text-xs text-neutral-600">Stockist Name</p>
                  <p className="font-medium text-neutral-800">{selectedInvoice.stockist_name || '-'}</p>
                </div>
                <div>
                  <p className="text-xs text-neutral-600">Stockist City</p>
                  <p className="font-medium text-neutral-800">{selectedInvoice.stockist_city || '-'}</p>
                </div>
                <div>
                  <p className="text-xs text-neutral-600">Sales Manager</p>
                  <p className="font-medium text-neutral-800">{selectedInvoice.sales_manager_name || '-'}</p>
                </div>
                <p className="text-xs text-neutral-400 md:col-span-3">Internal fields — not shown on the printed/PDF invoice.</p>
              </div>

              <div className="grid grid-cols-1 gap-4 rounded-lg border border-neutral-200 p-4 md:grid-cols-3">
                <div>
                  <p className="text-xs text-neutral-600">Subtotal</p>
                  <p className="font-medium">{formatAmount(selectedInvoice.subtotal)}</p>
                </div>
                <div>
                  <p className="text-xs text-neutral-600">Amount Paid</p>
                  <p className="font-medium text-green-700">{formatAmount(selectedInvoice.amount_paid)}</p>
                </div>
                <div>
                  <p className="text-xs text-neutral-600">Amount Due</p>
                  <p className="font-medium text-red-600">{selectedInvoice.amount_due > 0 ? formatAmount(selectedInvoice.amount_due) : '-'}</p>
                </div>
              </div>

              {selectedInvoice.notes && (
                <div>
                  <p className="mb-1 text-xs text-neutral-600">Notes</p>
                  <p className="rounded-lg bg-neutral-50 p-3 text-sm text-neutral-700">{selectedInvoice.notes}</p>
                </div>
              )}

              {selectedInvoiceItems.length > 0 && (
                <div>
                  <p className="mb-2 text-sm font-semibold text-neutral-700">Items</p>
                  <div className="overflow-x-auto rounded-lg border border-neutral-200">
                    <table className="w-full min-w-[700px] text-sm">
                      <thead>
                        <tr className="bg-neutral-50">
                          <th className="px-3 py-2 text-left">Product</th>
                          <th className="px-3 py-2 text-right">Qty</th>
                          <th className="px-3 py-2 text-right">Unit Price</th>
                          <th className="px-3 py-2 text-right">Discount %</th>
                          {selectedInvoice.invoice_type !== 'export_invoice' && <th className="px-3 py-2 text-right">{gstColumnLabel(selectedInvoice.invoice_type)}</th>}
                          <th className="px-3 py-2 text-right">Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedInvoiceItems.map((item) => {
                          const displayQty = item.net_quantity ?? item.quantity;
                          const displayTotal = item.net_total_amount ?? item.total_amount;
                          return (
                          <tr key={item.id} className="border-t border-neutral-100">
                            <td className="px-3 py-2">{item.description || productNameById(item.product_id)}</td>
                            <td className="px-3 py-2 text-right">{displayQty}</td>
                            <td className="px-3 py-2 text-right">{formatAmount(item.unit_price)}</td>
                            <td className="px-3 py-2 text-right">{item.discount_percent || 0}</td>
                            {selectedInvoice.invoice_type !== 'export_invoice' && <td className="px-3 py-2 text-right">{item.gst_rate}</td>}
                            <td className="px-3 py-2 text-right font-medium">{formatAmount(displayTotal)}</td>
                          </tr>
                          );
                        })}
                      </tbody>
                      <tfoot>
                        <tr className="border-t-2 bg-neutral-50">
                          <td colSpan={viewTotalLabelColSpan} className="px-3 py-2 text-right font-semibold">Total:</td>
                          <td className="px-3 py-2 text-right font-medium">{formatAmount(viewExactTotalPaise)}</td>
                        </tr>
                        {viewRoundOffPaise !== 0 && (
                          <tr className="bg-neutral-50">
                            <td colSpan={viewTotalLabelColSpan} className="px-3 py-2 text-right font-semibold">Round Off:</td>
                            <td className="px-3 py-2 text-right font-medium">{formatAmount(viewRoundOffPaise)}</td>
                          </tr>
                        )}
                        <tr className="bg-neutral-50">
                          <td colSpan={viewTotalLabelColSpan} className="px-3 py-2 text-right font-semibold">Grand Total:</td>
                          <td className="px-3 py-2 text-right font-bold text-primary">{formatAmount(viewRoundedTotalPaise)}</td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>
                </div>
              )}

              <div className="flex justify-end">
                <button onClick={() => setShowInvoiceDetail(false)} className="rounded-lg border border-neutral-200 bg-white px-4 py-2 text-sm font-semibold hover:bg-neutral-50">
                  Close
                </button>
              </div>
            </div>
          </div>,
          document.body
        )}
      </div>
    </AppLayout>
  );
};

export default InvoicesPage;


