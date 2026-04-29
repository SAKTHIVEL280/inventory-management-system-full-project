/**
 * Sales Invoices Page
 * List, create, edit, issue invoices. GST-aware line items.
 */
import { useState, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { AppLayout } from '../components/AppLayout';
import { salesApi, type SalesInvoice, type CreateInvoicePayload, type SalesLineItem, type SalesInvoiceItem, type InvoiceTypeValue, type InvoiceBatchOption } from '../api/sales';
import { apiClient } from '../api/client';
import { toast } from 'sonner';
import { confirmWithToast } from '../utils/toastHelper';
import { addDaysToDateInputValue, todayLocalDateInputValue } from '../utils/date';
import { emptyWhenZero } from '../utils/numberInput';

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

const InvoicesPage = () => {
  const [invoices, setInvoices] = useState<SalesInvoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
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

  const fetchInvoices = async () => {
    try { setLoading(true); const res = await salesApi.listInvoices(statusFilter || undefined); setInvoices(res.data.items || []); } catch { setError('Failed to load'); } finally { setLoading(false); }
  };
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

  // eslint-disable-next-line react-hooks/exhaustive-deps -- fetchInvoices should run when statusFilter changes
  useEffect(() => { fetchInvoices(); }, [statusFilter]);
  useEffect(() => { fetchMasterData(); }, []);

  const resetForm = () => { setCustomerId(''); setInvoiceType('within_state'); setImportExportCode(''); setInvoiceDate(todayLocalDateInputValue()); setDueDate(''); setIsDueDateManuallyEdited(false); setNotes(''); setItems([]); setBatchOptionsByRow({}); setEditingId(null); setError(''); };
  const addItem = () => {
    setItems([
      ...items,
      {
        product_id: '',
        order_unit: '',
        batch_no: '',
        manufacture_date: '',
        expiry_date: '',
        quantity: 1,
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
  const formatAmount = (p: number) => `₹${(p / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
  const deriveInvoicePaymentStatusLabel = (invoice?: Pick<SalesInvoice, 'status' | 'amount_paid' | 'total_amount'>) => {
    if (!invoice) return '-';
    const token = (invoice.status || '').trim().toLowerCase();
    if (token === 'draft') return 'Draft';
    if (token === 'cancelled') return 'Cancelled';

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
  const formatAvailableQty = (qty: number) => {
    if (!Number.isFinite(qty)) return '0';
    return Number(qty).toFixed(4).replace(/\.?0+$/, '');
  };

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

    setSubmitting(true); setError('');
    try {
      const payload: CreateInvoicePayload = {
        customer_id: customerId, invoice_date: invoiceDate,
        due_date: dueDate || undefined,
        bill_to_customer_id: customerId,
        invoice_type: invoiceType,
        import_export_code: importExportCode.trim() || undefined,
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
      if (editingId) {
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

  const customerNameById = (customerId: string) => {
    return customers.find((c) => c.id === customerId)?.company_name || 'Unknown customer';
  };
  const productNameById = (productId: string) => {
    return products.find((p) => p.id === productId)?.name || productId;
  };

  const filteredInvoices = invoices.filter((inv) => {
    const q = searchQuery.trim().toLowerCase();
    const customerName = customerNameById(inv.customer_id).toLowerCase();
    const matchesSearch =
      !q ||
      inv.invoice_number.toLowerCase().includes(q) ||
      customerName.includes(q) ||
      inv.status.toLowerCase().includes(q) ||
      inv.invoice_date.toLowerCase().includes(q) ||
      (inv.due_date || '').toLowerCase().includes(q);
    const matchesFrom = !dateFrom || inv.invoice_date >= dateFrom;
    const matchesTo = !dateTo || inv.invoice_date <= dateTo;
    return matchesSearch && matchesFrom && matchesTo;
  });

  return (
    <AppLayout title="Sales Invoices">
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <select className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
              <option value="">All</option><option value="draft">Draft</option><option value="issued">Issued</option><option value="partial_paid">Partial Paid</option><option value="paid">Paid</option><option value="cancelled">Cancelled</option>
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
          </div>
          <button onClick={() => { resetForm(); setShowForm(true); }} className="rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-primary/20 hover:bg-primary/90">+ New Invoice</button>
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
                : filteredInvoices.length === 0 ? <tr><td colSpan={9} className="px-4 py-8 text-center text-neutral-500">No invoices</td></tr>
                : filteredInvoices.map(inv => (
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
                        {inv.status === 'draft' && <button onClick={() => handleIssue(inv.id)} className="rounded px-2 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50">Issue</button>}
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
          {!loading && <p className="border-t border-neutral-200 px-4 py-3 text-xs text-neutral-500">Showing {filteredInvoices.length} of {invoices.length}</p>}
        </div>

        {showForm && createPortal(
          <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-2 sm:p-4 backdrop-blur-sm">
            <div className="hms-card my-4 sm:my-8 w-[min(96vw,1500px)] max-w-none space-y-6 p-4 sm:p-6">
              <h2 className="font-display text-xl font-bold">{editingId ? 'Modify/Change' : 'New'} Invoice</h2>
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
                  <table className="w-full min-w-[1760px] table-fixed text-sm">
                    <thead>
                      <tr className="bg-neutral-50">
                        <th className="w-[16%] px-3 py-2 text-left">Product</th>
                        <th className="w-[7%] px-3 py-2 text-left">Product Code</th>
                        <th className="w-[9%] px-3 py-2 text-left">Description</th>
                        <th className="w-[7%] px-3 py-2 text-left">Packing Unit</th>
                        <th className="w-[7%] px-3 py-2 text-left">Base Unit</th>
                        <th className="w-[7%] px-3 py-2 text-left">Batch</th>
                        <th className="w-[7%] px-3 py-2 text-left">MFG Date</th>
                        <th className="w-[7%] px-3 py-2 text-left">EXP Date</th>
                        <th className="w-[7%] px-3 py-2 text-left">HSN</th>
                        <th className="w-16 px-3 py-2 text-right">Qty</th>
                        <th className="w-16 px-3 py-2 text-right">Free</th>
                        <th className="w-28 px-3 py-2 text-right">MRP (₹)</th>
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
                        return (
                        <tr key={idx} className="border-t border-neutral-100">
                          <td className="px-3 py-2">
                            <select className="w-full rounded border px-2 py-1.5 text-sm" value={item.product_id} onChange={e => updateItem(idx, 'product_id', e.target.value)}>
                              <option value="">Select</option>
                              {products.map(p => <option key={p.id} value={p.id}>{p.name} ({p.product_code})</option>)}
                            </select>
                          </td>
                          {/* SAL-013: Product Code column */}
                          <td className="px-3 py-2 text-xs text-neutral-500 font-mono">{prod?.product_code || '-'}</td>
                          {/* SAL-014: Description column */}
                          <td className="px-3 py-2 text-xs text-neutral-500">{prod?.description || prod?.name || '-'}</td>
                          <td className="px-3 py-2">
                            <input type="text" className="w-full rounded border bg-neutral-50 px-2 py-1.5 text-sm text-neutral-700" value={item.order_unit || ''} readOnly placeholder="Auto from product" />
                          </td>
                          <td className="px-3 py-2">
                            <input type="text" className="w-full rounded border bg-neutral-50 px-2 py-1.5 text-sm text-neutral-700" value={resolveBaseUnit(prod)} readOnly placeholder="Auto from product" />
                          </td>
                          <td className="px-3 py-2">
                            {hasMultipleBatches ? (
                              <select
                                className="w-full rounded border px-2 py-1.5 text-sm"
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
                                className="w-full rounded border bg-neutral-50 px-2 py-1.5 text-sm text-neutral-700"
                                value={hasSingleBatch ? (item.batch_no || rowBatchOptions[0].batch_no) : ''}
                                readOnly
                                placeholder={item.product_id ? 'No batch available' : 'Select product first'}
                              />
                            )}
                          </td>
                          <td className="px-3 py-2">
                            <input type="date" className="w-full rounded border bg-neutral-50 px-2 py-1.5 text-sm text-neutral-700" value={item.manufacture_date || ''} readOnly />
                          </td>
                          <td className="px-3 py-2">
                            <input type="date" className="w-full rounded border bg-neutral-50 px-2 py-1.5 text-sm text-neutral-700" value={item.expiry_date || ''} readOnly />
                          </td>
                          {/* SAL-021: HSN Code column */}
                          <td className="px-3 py-2 text-xs text-neutral-500">{prod?.hsn_code || '-'}</td>
                          <td className="px-3 py-2">
                            <input type="number" min="0.01" step="0.01" className="w-full rounded border px-2 py-1.5 text-right text-sm" value={item.quantity} onChange={e => updateItem(idx, 'quantity', parseFloat(e.target.value) || 0)} />
                          </td>
                          <td className="px-3 py-2">
                            <input type="number" min="0" step="0.01" className="w-full rounded border px-2 py-1.5 text-right text-sm" value={emptyWhenZero(item.free_quantity)} onChange={e => updateItem(idx, 'free_quantity', parseFloat(e.target.value) || 0)} />
                          </td>
                          {/* SAL-020: MRP auto-fills from Product Master */}
                          <td className="px-3 py-2">
                            <input type="number" min="0" step="0.01" className="w-full rounded border px-2 py-1.5 text-right text-sm" value={item.unit_price ? paiseToRupees(item.unit_price) : ''} onChange={e => updateItem(idx, 'unit_price', rupeesToPaise(e.target.value))} />
                          </td>
                          <td className="px-3 py-2">
                            <input type="number" min="0" max="100" className="w-full rounded border px-2 py-1.5 text-right text-sm" value={emptyWhenZero(item.discount_percent)} onChange={e => updateItem(idx, 'discount_percent', parseFloat(e.target.value) || 0)} />
                          </td>
                          {!isExportInvoice && (
                            <td className="px-3 py-2">
                              <select className="w-full min-w-[60px] rounded border border-neutral-300 bg-white px-2 py-1.5 text-sm text-neutral-900 appearance-auto" value={item.gst_rate} onChange={e => updateItem(idx, 'gst_rate', parseInt(e.target.value))}>
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
                          <td className="px-3 py-2 text-right font-bold text-primary">{formatAmount(items.reduce((s, i) => s + calcTotal(i), 0))}</td>
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
                      onClick={() => {
                        setShowInvoiceDetail(false);
                        // Load into edit form
                        setEditingId(selectedInvoice.id);
                        setCustomerId(selectedInvoice.customer_id);
                        setInvoiceType((selectedInvoice.invoice_type as InvoiceTypeValue) || deriveDefaultInvoiceType(selectedInvoice.customer_id));
                        setImportExportCode(selectedInvoice.import_export_code || '');
                        setInvoiceDate(selectedInvoice.invoice_date);
                        setDueDate(selectedInvoice.due_date || '');
                        setIsDueDateManuallyEdited(true);
                        setNotes(selectedInvoice.notes || '');
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
                      }}
                      className="inline-flex items-center gap-1 rounded-lg border border-primary bg-primary/5 px-3 py-2 text-xs font-semibold text-primary hover:bg-primary/10"
                    >
                      <span className="material-icons text-sm" aria-hidden="true">edit</span>
                      Edit Invoice
                    </button>
                  )}
                  <button
                    onClick={() => handleDownloadPDF(selectedInvoice)}
                    className="inline-flex items-center gap-1 rounded-lg border border-neutral-200 bg-white px-3 py-2 text-xs font-semibold text-neutral-700 hover:bg-neutral-50"
                  >
                    <span className="material-icons text-sm" aria-hidden="true">picture_as_pdf</span>
                    Download PDF
                  </button>
                  <button onClick={() => setShowInvoiceDetail(false)} className="text-2xl text-neutral-400 hover:text-neutral-600">&times;</button>
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
                        {selectedInvoiceItems.map((item) => (
                          <tr key={item.id} className="border-t border-neutral-100">
                            <td className="px-3 py-2">{item.description || productNameById(item.product_id)}</td>
                            <td className="px-3 py-2 text-right">{item.quantity}</td>
                            <td className="px-3 py-2 text-right">{formatAmount(item.unit_price)}</td>
                            <td className="px-3 py-2 text-right">{item.discount_percent || 0}</td>
                            {selectedInvoice.invoice_type !== 'export_invoice' && <td className="px-3 py-2 text-right">{item.gst_rate}</td>}
                            <td className="px-3 py-2 text-right font-medium">{formatAmount(item.total_amount)}</td>
                          </tr>
                        ))}
                      </tbody>
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


