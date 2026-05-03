/**
 * Reports Page
 * Visual analytics hub with charts, tables, and financial summaries.
 * Uses Recharts for data visualization.
 */
import { Fragment, useEffect, useMemo, useState } from 'react';
import { AppLayout } from '../components/AppLayout';
import { BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { apiClient, type ApiRequestConfig } from '../api/client';
import { downloadGSTR1Export, downloadGSTR2Export, downloadGSTReconciliationExport, getGstAuditTrail, getGSTR1Report, getGSTR2Report, getGSTReconciliationReport, type GSTAuditTrailResponse, type GSTR1ReportDetailRow, type GSTR1ReportResponse, type GSTR2ReportDetailRow, type GSTR2ReportResponse, type GSTReconciliationResponse } from '../api/reports';
import { toLocalDateInputValue } from '../utils/date';
import { useAuthStore } from '../store/auth';

interface PLData { net_sales: number; purchases: number; gross_profit: number; gross_profit_margin_percent: number; net_profit: number; }
interface StockItem {
  product_code: string;
  product_name: string;
  hsn: string;
  batch_no: string | null;
  manufacture_date: string | null;
  expiry_date: string | null;
  closing_qty: number;
  min_stock: number;
  status: string;
}
interface SalesReportItem { invoice_number: string; invoice_date: string; total_amount: number; amount_paid: number; amount_due: number; status: string; }
interface GSTR3BData { output_tax: number; itc: number; net_tax_payable: number; }
type ReportFrequency = 'monthly' | 'quarterly' | 'annually';
interface ApiErrorShape {
  response?: {
    status?: number;
    data?: {
      detail?: unknown;
    };
  };
  message?: string;
}

const formatAmount = (p: number) => `₹${(p / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
const formatDecimalAmount = (amount: number) => `₹${amount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const formatQuantity = (value: number | null | undefined) => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return '-';
  return numeric.toLocaleString('en-IN', { maximumFractionDigits: 3 });
};
const formatTaxPercent = (value: number | null) => (value == null ? '-' : value.toFixed(2));
const formatAuditTimestamp = (value: string | null) => {
  if (!value) return '-';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  });
};

const toInputDate = (d: Date) => toLocalDateInputValue(d);

const getFrequencyDateWindow = (frequency: ReportFrequency, baseDate: Date) => {
  const year = baseDate.getFullYear();
  const month = baseDate.getMonth();
  if (frequency === 'monthly') {
    const start = new Date(year, month, 1);
    const end = new Date(year, month + 1, 0);
    return { from: toInputDate(start), to: toInputDate(end) };
  }
  if (frequency === 'quarterly') {
    const quarterStartMonth = Math.floor(month / 3) * 3;
    const start = new Date(year, quarterStartMonth, 1);
    const end = new Date(year, quarterStartMonth + 3, 0);
    return { from: toInputDate(start), to: toInputDate(end) };
  }
  const start = new Date(year, 0, 1);
  const end = new Date(year, 11, 31);
  return { from: toInputDate(start), to: toInputDate(end) };
};

const parseLocalDate = (value: string): Date | null => {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const [yearToken, monthToken, dayToken] = value.split('-');
  const year = Number(yearToken);
  const month = Number(monthToken);
  const day = Number(dayToken);
  if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) return null;
  const parsed = new Date(year, month - 1, day);
  parsed.setHours(0, 0, 0, 0);
  return parsed;
};

const FREQUENCY_OPTIONS: { value: ReportFrequency; label: string }[] = [
  { value: 'monthly', label: 'Monthly' },
  { value: 'quarterly', label: 'Quarterly' },
  { value: 'annually', label: 'Annually' },
];

const getErrorMessage = (reason: unknown): string => {
  const error = reason as ApiErrorShape;
  const status = error?.response?.status;
  const detail = error?.response?.data?.detail;

  let msg = '';
  if (typeof detail === 'string') {
    msg = detail;
  } else if (Array.isArray(detail)) {
    msg = detail
      .map((d) => {
        if (d && typeof d === 'object' && 'msg' in d && typeof (d as { msg?: string }).msg === 'string') {
          return (d as { msg: string }).msg;
        }
        return '';
      })
      .filter(Boolean)
      .join(', ');
  } else if (detail && typeof detail === 'object' && 'message' in detail && typeof (detail as { message?: string }).message === 'string') {
    msg = (detail as { message: string }).message;
  } else if (typeof error?.message === 'string') {
    msg = error.message;
  }

  if (status && msg) {
    return `${status}: ${msg}`;
  }
  if (status) {
    return `${status}`;
  }
  return msg || 'request failed';
};

const withTimeout = <T,>(promise: Promise<T>, timeoutMs = 15000, label = 'Request'): Promise<T> => {
  return new Promise<T>((resolve, reject) => {
    const timeoutId = window.setTimeout(() => {
      reject(new Error(`${label} timed out after ${timeoutMs}ms`));
    }, timeoutMs);

    promise
      .then((result) => {
        window.clearTimeout(timeoutId);
        resolve(result);
      })
      .catch((error) => {
        window.clearTimeout(timeoutId);
        reject(error);
      });
  });
};

const ReportsPage = () => {
  const user = useAuthStore((state) => state.user);
  const today = new Date();
  const defaultWindow = getFrequencyDateWindow('monthly', today);
  const [dateRange, setDateRange] = useState<{ from: string; to: string }>({
    from: defaultWindow.from,
    to: defaultWindow.to,
  });
  const [reportFrequency, setReportFrequency] = useState<ReportFrequency>('monthly');
  const [activeTab, setActiveTab] = useState<'overview' | 'sales' | 'stock' | 'gst' | 'pl'>('overview');
  const [loading, setLoading] = useState(false);
  const [fetchWarning, setFetchWarning] = useState('');
  const [dateInputError, setDateInputError] = useState('');

  // Data
  const [dashboard, setDashboard] = useState<Record<string, unknown> | null>(null);
  const [plData, setPLData] = useState<PLData | null>(null);
  const [stockItems, setStockItems] = useState<StockItem[]>([]);
  const [salesItems, setSalesItems] = useState<SalesReportItem[]>([]);
  const [salesTotal, setSalesTotal] = useState(0);
  const [gstData, setGstData] = useState<GSTR1ReportResponse | null>(null);
  const [gstr2Data, setGstr2Data] = useState<GSTR2ReportResponse | null>(null);
  const [gstReconciliationData, setGstReconciliationData] = useState<GSTReconciliationResponse | null>(null);
  const [gstAuditTrail, setGstAuditTrail] = useState<GSTAuditTrailResponse | null>(null);
  const [gstr3bData, setGstr3bData] = useState<GSTR3BData | null>(null);
  const [auditReportType, setAuditReportType] = useState<'all' | 'gstr1' | 'gstr2' | 'gstr3b' | 'reconciliation'>('all');
  const [auditPage, setAuditPage] = useState(1);
  const [auditPageSize, setAuditPageSize] = useState(20);
  const [expandedGstr1Invoices, setExpandedGstr1Invoices] = useState<Record<string, boolean>>({});
  const [expandedGstr2Grns, setExpandedGstr2Grns] = useState<Record<string, boolean>>({});
  const isFinanceTaxUser = (user?.role || '').toLowerCase() === 'admin' || (user?.role || '').toLowerCase() === 'accounting';
  const fromDate = dateRange.from;
  const toDate = dateRange.to;

  const getAlignedWindow = (frequency: ReportFrequency, anchorValue: string, fallbackValue: string) => {
    const anchorDate = parseLocalDate(anchorValue) || parseLocalDate(fallbackValue) || new Date();
    return getFrequencyDateWindow(frequency, anchorDate);
  };

  const gstr1DetailMap = useMemo(() => {
    const map = new Map<string, GSTR1ReportDetailRow[]>();
    (gstData?.detail_items || []).forEach((item) => {
      const key = item.sales_invoice_no || '';
      if (!key) return;
      const existing = map.get(key) || [];
      existing.push(item);
      map.set(key, existing);
    });
    return map;
  }, [gstData?.detail_items]);

  const gstr2DetailMap = useMemo(() => {
    const map = new Map<string, GSTR2ReportDetailRow[]>();
    (gstr2Data?.detail_items || []).forEach((item) => {
      const key = item.grn_no || '';
      if (!key) return;
      const existing = map.get(key) || [];
      existing.push(item);
      map.set(key, existing);
    });
    return map;
  }, [gstr2Data?.detail_items]);

  const toggleGstr1Details = (invoiceNo: string) => {
    setExpandedGstr1Invoices((prev) => ({
      ...prev,
      [invoiceNo]: !prev[invoiceNo],
    }));
  };

  const toggleGstr2Details = (grnNo: string) => {
    setExpandedGstr2Grns((prev) => ({
      ...prev,
      [grnNo]: !prev[grnNo],
    }));
  };

  const handleFromDateChange = (value: string) => {
    setAuditPage(1);
    setDateRange(getAlignedWindow(reportFrequency, value, toDate));
  };

  const handleToDateChange = (value: string) => {
    setAuditPage(1);
    setDateRange(getAlignedWindow(reportFrequency, value, fromDate));
  };

  const handleFrequencyChange = (value: ReportFrequency) => {
    const window = getAlignedWindow(value, fromDate, toDate);
    setReportFrequency(value);
    setAuditPage(1);
    setDateRange({ from: window.from, to: window.to });
    setDateInputError('');
    setFetchWarning('');
  };

  const handleAuditReportTypeChange = (value: 'all' | 'gstr1' | 'gstr2' | 'gstr3b' | 'reconciliation') => {
    setAuditReportType(value);
    setAuditPage(1);
  };

  const handleAuditPageSizeChange = (value: number) => {
    setAuditPageSize(value);
    setAuditPage(1);
  };

  const validateFrequencyRangeOnClient = (): string | null => {
    if (!fromDate || !toDate) {
      return 'From date and To date are required.';
    }
    if (fromDate > toDate) {
      return 'Invalid date range: From date cannot be after To date.';
    }
    const start = parseLocalDate(fromDate);
    const end = parseLocalDate(toDate);
    if (!start || !end) {
      return 'Please select valid dates.';
    }

    const expected = getFrequencyDateWindow(reportFrequency, start);
    if (expected.from !== fromDate || expected.to !== toDate) {
      const label = reportFrequency === 'monthly' ? 'Monthly' : reportFrequency === 'quarterly' ? 'Quarterly' : 'Annual';
      return `${label} range must match the exact selected period boundaries.`;
    }
    return null;
  };

  const fetchAll = async () => {
    setLoading(true);
    setFetchWarning('');

    const failedSections: string[] = [];
    const shouldLoadGst = isFinanceTaxUser && activeTab === 'gst';
    try {
      // Fast pre-check so backend downtime does not keep the page in long loading cycles.
      const healthConfig: ApiRequestConfig = { timeout: 4000, skipErrorToast: true };
      await withTimeout(apiClient.get('/health', healthConfig), 4500, 'Backend health');

      const gstPromise = shouldLoadGst ? withTimeout(getGSTR1Report(fromDate, toDate, reportFrequency), 20000, 'GSTR-1') : Promise.resolve(null);
      const gstr2Promise = shouldLoadGst ? withTimeout(getGSTR2Report(fromDate, toDate, reportFrequency), 20000, 'GSTR-2') : Promise.resolve(null);
      const reconciliationPromise = shouldLoadGst ? withTimeout(getGSTReconciliationReport(fromDate, toDate, reportFrequency), 20000, 'GST Reconciliation') : Promise.resolve(null);
      const auditTrailPromise = shouldLoadGst
        ? getGstAuditTrail(fromDate, toDate, reportFrequency, auditReportType, auditPage, auditPageSize)
        : Promise.resolve(null);
      const gstr3bPromise = shouldLoadGst
        ? apiClient.get('/api/v2/reports/gstr3b', { params: { from_date: fromDate, to_date: toDate } })
        : Promise.resolve(null);

      const [dashRes, plRes, stockRes, salesRes, gstRes, gstr2Res, reconciliationRes, auditTrailRes, gstr3bRes] = await Promise.allSettled([
        withTimeout(apiClient.get('/api/v2/reports/dashboard'), 15000, 'Dashboard'),
        withTimeout(apiClient.get('/api/v2/reports/pl', { params: { from_date: fromDate, to_date: toDate } }), 15000, 'P&L'),
        withTimeout(apiClient.get('/api/v2/reports/stock'), 15000, 'Stock'),
        withTimeout(apiClient.get('/api/v2/reports/sales', { params: { from_date: fromDate, to_date: toDate } }), 15000, 'Sales'),
        gstPromise,
        gstr2Promise,
        reconciliationPromise,
        shouldLoadGst ? withTimeout(auditTrailPromise, 20000, 'GST Audit Trail') : auditTrailPromise,
        shouldLoadGst ? withTimeout(gstr3bPromise, 20000, 'GSTR-3B') : gstr3bPromise,
      ]);

      if (dashRes.status === 'fulfilled') {
        setDashboard((dashRes.value.data as Record<string, unknown>) || null);
      } else {
        setDashboard(null);
        failedSections.push(`Dashboard (${getErrorMessage(dashRes.reason)})`);
      }

      if (plRes.status === 'fulfilled') {
        setPLData((plRes.value.data as PLData) || null);
      } else {
        setPLData(null);
        failedSections.push(`P&L (${getErrorMessage(plRes.reason)})`);
      }

      if (stockRes.status === 'fulfilled') {
        setStockItems((stockRes.value.data?.items as StockItem[]) || []);
      } else {
        setStockItems([]);
        failedSections.push(`Stock (${getErrorMessage(stockRes.reason)})`);
      }

      if (salesRes.status === 'fulfilled') {
        setSalesItems((salesRes.value.data?.items as SalesReportItem[]) || []);
        setSalesTotal(Number(salesRes.value.data?.total_amount) || 0);
      } else {
        setSalesItems([]);
        setSalesTotal(0);
        failedSections.push(`Sales (${getErrorMessage(salesRes.reason)})`);
      }

      if (!shouldLoadGst) {
        setGstData(null);
      } else if (gstRes.status === 'fulfilled') {
        setGstData((gstRes.value as GSTR1ReportResponse) || null);
      } else {
        setGstData(null);
        failedSections.push(`GSTR-1 (${getErrorMessage(gstRes.reason)})`);
      }

      if (!shouldLoadGst) {
        setGstr2Data(null);
      } else if (gstr2Res.status === 'fulfilled') {
        setGstr2Data((gstr2Res.value as GSTR2ReportResponse) || null);
      } else {
        setGstr2Data(null);
        failedSections.push(`GSTR-2 (${getErrorMessage(gstr2Res.reason)})`);
      }

      if (!shouldLoadGst) {
        setGstReconciliationData(null);
      } else if (reconciliationRes.status === 'fulfilled') {
        setGstReconciliationData((reconciliationRes.value as GSTReconciliationResponse) || null);
      } else {
        setGstReconciliationData(null);
        failedSections.push(`GST Reconciliation (${getErrorMessage(reconciliationRes.reason)})`);
      }

      if (!shouldLoadGst) {
        setGstAuditTrail(null);
      } else if (auditTrailRes.status === 'fulfilled') {
        setGstAuditTrail((auditTrailRes.value as GSTAuditTrailResponse) || null);
      } else {
        setGstAuditTrail(null);
        failedSections.push(`GST Audit Trail (${getErrorMessage(auditTrailRes.reason)})`);
      }

      if (!shouldLoadGst) {
        setGstr3bData(null);
      } else if (gstr3bRes.status === 'fulfilled') {
        setGstr3bData(((gstr3bRes.value as { data?: GSTR3BData }).data as GSTR3BData) || null);
      } else {
        setGstr3bData(null);
        failedSections.push(`GSTR-3B (${getErrorMessage(gstr3bRes.reason)})`);
      }

      if (failedSections.length > 0) {
        setFetchWarning(`Some sections failed to load: ${failedSections.join(', ')}`);
      }
    } catch (error) {
      const message = getErrorMessage(error);
      if (
        message.toLowerCase().includes('cannot reach server')
        || message.toLowerCase().includes('network')
        || message.toLowerCase().includes('timed out')
      ) {
        setFetchWarning('Backend is unreachable. Start backend server and retry.');
      } else {
        setFetchWarning(`Failed to load reports data: ${message}`);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleReconciliationExport = async (format: 'xlsx' | 'pdf') => {
    try {
      const blob = await downloadGSTReconciliationExport(fromDate, toDate, reportFrequency, format);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `gst_reconciliation_${fromDate}_${toDate}.${format}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      // Refresh GST Audit Trail to show the new export event immediately (page 1)
      try {
        setAuditPage(1);
        const refreshed = await withTimeout(getGstAuditTrail(fromDate, toDate, reportFrequency, auditReportType, 1, auditPageSize), 10000, 'Refresh GST Audit Trail');
        setGstAuditTrail((refreshed as GSTAuditTrailResponse) || null);
      } catch (err) {
        // Non-fatal: ignore refresh errors but log for debugging
        console.debug('Failed to refresh GST Audit Trail after export:', err);
      }
    } catch {
      setFetchWarning('Failed to export GST reconciliation report. Please retry.');
    }
  };

  const handleGstr1Export = async (format: 'xlsx' | 'pdf') => {
    try {
      const blob = await downloadGSTR1Export(fromDate, toDate, reportFrequency, format);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `gstr1_${fromDate}_${toDate}.${format}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      // Refresh GST Audit Trail to show the new export event immediately (page 1)
      try {
        setAuditPage(1);
        const refreshed = await withTimeout(getGstAuditTrail(fromDate, toDate, reportFrequency, auditReportType, 1, auditPageSize), 10000, 'Refresh GST Audit Trail');
        setGstAuditTrail((refreshed as GSTAuditTrailResponse) || null);
      } catch (err) {
        console.debug('Failed to refresh GST Audit Trail after GSTR-1 export:', err);
      }
    } catch {
      setFetchWarning('Failed to export GSTR-1 report. Please retry.');
    }
  };

  const handleGstr2Export = async (format: 'xlsx' | 'pdf') => {
    try {
      const blob = await downloadGSTR2Export(fromDate, toDate, reportFrequency, format);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `gstr2_${fromDate}_${toDate}.${format}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      // Refresh GST Audit Trail to show the new export event immediately (page 1)
      try {
        setAuditPage(1);
        const refreshed = await withTimeout(getGstAuditTrail(fromDate, toDate, reportFrequency, auditReportType, 1, auditPageSize), 10000, 'Refresh GST Audit Trail');
        setGstAuditTrail((refreshed as GSTAuditTrailResponse) || null);
      } catch (err) {
        console.debug('Failed to refresh GST Audit Trail after GSTR-2 export:', err);
      }
    } catch {
      setFetchWarning('Failed to export GSTR-2 report. Please retry.');
    }
  };

  useEffect(() => {
    setExpandedGstr1Invoices({});
  }, [gstData?.items]);

  useEffect(() => {
    setExpandedGstr2Grns({});
  }, [gstr2Data?.items]);

  // eslint-disable-next-line react-hooks/exhaustive-deps -- debounce filter updates to avoid flicker and intermediate validation
  useEffect(() => {
    const timer = window.setTimeout(() => {
      const frequencyValidationError = validateFrequencyRangeOnClient();
      if (frequencyValidationError) {
        setDateInputError(frequencyValidationError);
        setLoading(false);
        return;
      }
      setDateInputError('');
      fetchAll();
    }, 250);

    return () => window.clearTimeout(timer);
  }, [
    fromDate,
    toDate,
    reportFrequency,
    auditReportType,
    auditPage,
    auditPageSize,
    activeTab,
  ]);

  const salesTrend = (dashboard as Record<string, unknown>)?.sales_trend as { date: string; amount: number }[] || [];
  const topProducts = (dashboard as Record<string, unknown>)?.top_products as { product_name: string; quantity_sold: number; amount: number }[] || [];

  const stockSummary = [
    { name: 'In Stock', value: stockItems.filter(i => i.status === 'In Stock').length },
    { name: 'Below Safety Stock', value: stockItems.filter(i => i.status === 'Below Safety Stock').length },
    { name: 'Low Stock', value: stockItems.filter(i => i.status === 'Low Stock').length },
    { name: 'Out of Stock', value: stockItems.filter(i => i.status === 'Out of Stock').length },
  ].filter(i => i.value > 0);

  const tabs = [
    { key: 'overview', label: 'Overview' },
    { key: 'sales', label: 'Sales Report' },
    { key: 'stock', label: 'Stock Report' },
    { key: 'gst', label: 'GST Report' },
    { key: 'pl', label: 'Profit & Loss' },
  ] as const;

  return (
    <AppLayout title="Reports & Analytics">
      <div className="space-y-6">
        {/* Date Range + Tabs */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            {tabs.map(t => (
              <button key={t.key} onClick={() => setActiveTab(t.key)}
                className={`rounded-lg px-4 py-2 text-sm font-semibold transition ${activeTab === t.key ? 'bg-primary text-white' : 'bg-white text-neutral-600 border border-neutral-200 hover:bg-neutral-50'}`}
              >{t.label}</button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <select
              className="rounded-lg border border-neutral-200 px-3 py-2 text-sm"
              value={reportFrequency}
              onChange={e => handleFrequencyChange(e.target.value as ReportFrequency)}
            >
              {FREQUENCY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
            <input
              type="date"
              className="rounded-lg border border-neutral-200 px-3 py-2 text-sm"
              value={fromDate}
              onChange={e => handleFromDateChange(e.target.value)}
            />
            <span className="text-sm text-neutral-500">to</span>
            <input
              type="date"
              className="rounded-lg border border-neutral-200 px-3 py-2 text-sm"
              value={toDate}
              min={fromDate || undefined}
              onChange={e => handleToDateChange(e.target.value)}
            />
          </div>
          {dateInputError && (
            <div className="w-full text-right text-sm text-rose-700">
              {dateInputError}
            </div>
          )}
        </div>

        {fetchWarning && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
            {fetchWarning}
          </div>
        )}

        {loading && <div className="py-12 text-center text-neutral-500">Loading reports...</div>}

        {/* Overview Tab */}
        {!loading && activeTab === 'overview' && (
          <div className="space-y-6">
            {/* KPI Cards */}
            <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
              <div className="hms-card p-5">
                <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Today Sales</p>
                <p className="mt-2 text-2xl font-bold text-primary">{formatAmount(Number((dashboard as Record<string, unknown>)?.today_sales) || 0)}</p>
              </div>
              <div className="hms-card p-5">
                <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Month Sales</p>
                <p className="mt-2 text-2xl font-bold text-primary">{formatAmount(Number((dashboard as Record<string, unknown>)?.month_sales) || 0)}</p>
              </div>
              <div className="hms-card p-5">
                <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Outstanding Receivables</p>
                <p className="mt-2 text-2xl font-bold text-red-600">{formatAmount(Number((dashboard as Record<string, unknown>)?.outstanding_receivables) || 0)}</p>
              </div>
              <div className="hms-card p-5">
                <p className="text-xs font-bold uppercase tracking-wider text-neutral-500">Overdue Invoices</p>
                <p className="mt-2 text-2xl font-bold text-amber-600">{Number((dashboard as Record<string, unknown>)?.overdue_invoices_count) || 0}</p>
              </div>
            </div>

            {/* Charts Row */}
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              {/* Sales Trend */}
              <div className="hms-card p-6">
                <h3 className="mb-4 text-sm font-bold text-neutral-700">Sales Trend (Last 7 Days)</h3>
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart data={salesTrend}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 12 }} tickFormatter={v => `₹${(v/100).toFixed(0)}`} />
                    <Tooltip formatter={(v: number) => formatAmount(v)} />
                    <Line type="monotone" dataKey="amount" stroke="#1E3A5F" strokeWidth={2} dot={{ fill: '#1E3A5F' }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              {/* Stock Distribution */}
              <div className="hms-card p-6">
                <h3 className="mb-4 text-sm font-bold text-neutral-700">Stock Status Distribution</h3>
                <ResponsiveContainer width="100%" height={250}>
                  <PieChart>
                    <Pie data={stockSummary} cx="50%" cy="50%" labelLine={false} label={({ name, value }) => `${name}: ${value}`}
                      outerRadius={80} dataKey="value">
                      {stockSummary.map((_, idx) => <Cell key={idx} fill={['#22c55e', '#38bdf8', '#f59e0b', '#ef4444'][idx]} />)}
                    </Pie>
                    <Tooltip />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Top Products */}
            {topProducts.length > 0 && (
              <div className="hms-card p-6">
                <h3 className="mb-4 text-sm font-bold text-neutral-700">Top Selling Products (This Month)</h3>
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={topProducts}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis dataKey="product_name" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Bar dataKey="quantity_sold" fill="#2E86AB" name="Qty Sold" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        )}

        {/* Sales Report Tab */}
        {!loading && activeTab === 'sales' && (
          <div className="space-y-4">
            <div className="hms-card p-5">
              <p className="text-sm text-neutral-500">Total Sales ({fromDate} to {toDate})</p>
              <p className="mt-1 text-2xl font-bold text-primary">{formatAmount(salesTotal)}</p>
              <p className="text-xs text-neutral-500">{salesItems.length} invoice(s)</p>
            </div>
            {salesItems.length === 0 && (
              <div className="hms-card px-5 py-4 text-sm text-neutral-600">
                No sales invoices found for selected date range. Expand the range to include older invoices.
              </div>
            )}
            <div className="hms-card overflow-hidden">
              <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b bg-neutral-50"><th className="px-4 py-3 text-left font-semibold">Invoice #</th><th className="px-4 py-3 text-left font-semibold">Date</th><th className="px-4 py-3 text-right font-semibold">Amount</th><th className="px-4 py-3 text-right font-semibold">Paid</th><th className="px-4 py-3 text-right font-semibold">Due</th><th className="px-4 py-3 text-center font-semibold">Status</th></tr></thead>
                <tbody>
                  {salesItems.length === 0 ? (
                    <tr><td colSpan={6} className="px-4 py-6 text-center text-neutral-500">No rows to display for selected range.</td></tr>
                  ) : salesItems.map((i, idx) => (<tr key={idx} className="border-b border-neutral-100"><td className="px-4 py-3">{i.invoice_number}</td><td className="px-4 py-3">{i.invoice_date}</td><td className="px-4 py-3 text-right">{formatAmount(i.total_amount)}</td><td className="px-4 py-3 text-right text-green-600">{formatAmount(i.amount_paid)}</td><td className="px-4 py-3 text-right text-red-600">{i.amount_due > 0 ? formatAmount(i.amount_due) : '-'}</td><td className="px-4 py-3 text-center"><span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-semibold text-blue-700">{i.status}</span></td></tr>))}
                </tbody>
              </table></div>
            </div>
          </div>
        )}

        {/* Stock Report Tab */}
        {!loading && activeTab === 'stock' && (
          <div className="hms-card overflow-hidden">
            <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b bg-neutral-50"><th className="px-4 py-3 text-left font-semibold">Code</th><th className="px-4 py-3 text-left font-semibold">Product</th><th className="px-4 py-3 text-left font-semibold">Batch No</th><th className="px-4 py-3 text-left font-semibold">MFG Date</th><th className="px-4 py-3 text-left font-semibold">EXP Date</th><th className="px-4 py-3 text-right font-semibold">Qty</th><th className="px-4 py-3 text-right font-semibold">Min</th><th className="px-4 py-3 text-center font-semibold">Status</th></tr></thead>
              <tbody>{stockItems.map((i, idx) => {
                const sc: Record<string, string> = {
                  'In Stock': 'bg-green-100 text-green-700',
                  'Below Safety Stock': 'bg-sky-100 text-sky-700',
                  'Low Stock': 'bg-amber-100 text-amber-700',
                  'Out of Stock': 'bg-red-100 text-red-700'
                };
                return (<tr key={idx} className="border-b border-neutral-100"><td className="px-4 py-3">{i.product_code}</td><td className="px-4 py-3">{i.product_name}</td><td className="px-4 py-3">{i.batch_no || '-'}</td><td className="px-4 py-3">{i.manufacture_date || '-'}</td><td className="px-4 py-3">{i.expiry_date || '-'}</td><td className="px-4 py-3 text-right">{i.closing_qty}</td><td className="px-4 py-3 text-right text-neutral-500">{i.min_stock}</td><td className="px-4 py-3 text-center"><span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${sc[i.status]}`}>{i.status}</span></td></tr>);
              })}</tbody>
            </table></div>
            <p className="border-t px-4 py-3 text-xs text-neutral-500">{stockItems.length} batch rows</p>
          </div>
        )}

        {/* GST Report Tab */}
        {!loading && activeTab === 'gst' && (
          <div className="space-y-6">
            {!isFinanceTaxUser && (
              <div className="hms-card px-5 py-4 text-sm text-neutral-600">
                GST reports are restricted to Finance/Tax users (Admin or Accounting role).
              </div>
            )}
            {isFinanceTaxUser && !gstData && !gstr2Data && !gstReconciliationData && !gstr3bData && (
              <div className="hms-card px-5 py-4 text-sm text-neutral-600">
                GST report data is unavailable for the selected range. If data exists in invoices/GRNs, expand the date range or check access permissions.
              </div>
            )}
            {gstData && (
              <div className="hms-card overflow-hidden">
                <div className="border-b border-neutral-200 bg-neutral-50 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h3 className="text-sm font-bold text-neutral-800">{gstData.report_title}</h3>
                    <div className="flex items-center gap-2">
                      <button type="button" onClick={() => handleGstr1Export('xlsx')} className="rounded border border-neutral-300 bg-white px-3 py-1 text-xs font-semibold text-neutral-700 hover:bg-neutral-100">Export XLSX</button>
                      <button type="button" onClick={() => handleGstr1Export('pdf')} className="rounded border border-neutral-300 bg-white px-3 py-1 text-xs font-semibold text-neutral-700 hover:bg-neutral-100">Export PDF</button>
                    </div>
                  </div>
                  <p className="mt-1 text-xs text-neutral-600">
                    Period: {gstData.from_date_display || fromDate} to {gstData.to_date_display || toDate} | Frequency: {gstData.frequency_label} | Rows: {gstData.count}
                  </p>
                  {!!gstData.validation_error_count && gstData.validation_error_count > 0 && (
                    <div className="mt-2 rounded border border-amber-300 bg-amber-50 px-2 py-2 text-xs text-amber-800">
                      <p>Validation warnings: {gstData.validation_error_count}. All records are included in totals; review highlighted issues.</p>
                      {gstData.problematic_records && gstData.problematic_records.length > 0 && (
                        <ul className="mt-1 list-disc pl-4">
                          {gstData.problematic_records.slice(0, 5).map((record) => (
                            <li key={`gstr1-${record.document_no}-${record.document_date || 'na'}`}>
                              {record.document_type.toUpperCase()} {record.document_no || '(missing number)'}: {(record.errors || []).slice(0, 2).join(' | ')}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-neutral-100 text-xs uppercase tracking-wide text-neutral-600">
                        <th className="px-3 py-2 text-left">S.No</th>
                        <th className="px-3 py-2 text-left">Sales Invoice Date</th>
                        <th className="px-3 py-2 text-left">Sales Invoice No</th>
                        <th className="px-3 py-2 text-left">Name of the Bill to Party</th>
                        <th className="px-3 py-2 text-left">Bill to Party GSTIN No</th>
                        <th className="px-3 py-2 text-left">Place of Supply</th>
                        <th className="px-3 py-2 text-left">Name of the Ship to Party</th>
                        <th className="px-3 py-2 text-right">Invoice Amount</th>
                        <th className="px-3 py-2 text-center">Currency</th>
                        <th className="px-3 py-2 text-right">Tax %</th>
                        <th className="px-3 py-2 text-right">CGST Amount</th>
                        <th className="px-3 py-2 text-right">SGST Amount</th>
                        <th className="px-3 py-2 text-right">IGST Amount</th>
                        <th className="px-3 py-2 text-right">UGST Amount</th>
                        <th className="px-3 py-2 text-right">Export</th>
                        <th className="px-3 py-2 text-right">Total Tax Amount</th>
                        <th className="px-3 py-2 text-center">Details</th>
                      </tr>
                    </thead>
                    <tbody>
                      {gstData.items.length === 0 ? (
                        <tr>
                          <td colSpan={17} className="px-4 py-6 text-center text-neutral-500">
                            No sales transactions found for selected filters.
                          </td>
                        </tr>
                      ) : (
                        gstData.items.map((row) => {
                          const detailRows = gstr1DetailMap.get(row.sales_invoice_no) || [];
                          const isExpanded = Boolean(expandedGstr1Invoices[row.sales_invoice_no]);
                          return (
                            <Fragment key={`${row.sales_invoice_no}-${row.s_no}`}>
                              <tr className="border-b border-neutral-100">
                                <td className="px-3 py-2 text-left">{row.s_no}</td>
                                <td className="px-3 py-2 text-left">{row.sales_invoice_date || '-'}</td>
                                <td className="px-3 py-2 text-left">{row.sales_invoice_no}</td>
                                <td className="px-3 py-2 text-left">{row.bill_to_party_name}</td>
                                <td className="px-3 py-2 text-left font-mono text-xs break-all">{row.bill_to_party_gstin_no}</td>
                                <td className="px-3 py-2 text-left">{row.place_of_supply}</td>
                                <td className="px-3 py-2 text-left">{row.ship_to_party_name}</td>
                                <td className="px-3 py-2 text-right">{formatDecimalAmount(row.invoice_amount)}</td>
                                <td className="px-3 py-2 text-center">{row.currency}</td>
                                <td className="px-3 py-2 text-right">{formatTaxPercent(row.tax_percent)}</td>
                                <td className="px-3 py-2 text-right">{formatDecimalAmount(row.cgst_amount)}</td>
                                <td className="px-3 py-2 text-right">{formatDecimalAmount(row.sgst_amount)}</td>
                                <td className="px-3 py-2 text-right">{formatDecimalAmount(row.igst_amount)}</td>
                                <td className="px-3 py-2 text-right">{formatDecimalAmount(row.ugst_amount)}</td>
                                <td className="px-3 py-2 text-right">{formatDecimalAmount(row.export_amount)}</td>
                                <td className="px-3 py-2 text-right font-semibold">{formatDecimalAmount(row.total_tax_amount)}</td>
                                <td className="px-3 py-2 text-center">
                                  <button
                                    type="button"
                                    onClick={() => toggleGstr1Details(row.sales_invoice_no)}
                                    className="rounded border border-neutral-300 bg-white px-2 py-1 text-xs font-semibold text-neutral-700 hover:bg-neutral-100"
                                  >
                                    {isExpanded ? 'Hide Details' : 'View Details'}
                                  </button>
                                </td>
                              </tr>
                              {isExpanded && (
                                <tr className="bg-neutral-50">
                                  <td colSpan={17} className="px-3 py-3">
                                    {detailRows.length === 0 ? (
                                      <div className="text-xs text-neutral-500">No product details available for this invoice.</div>
                                    ) : (
                                      <div className="overflow-x-auto">
                                        <table className="w-full text-xs">
                                          <thead>
                                            <tr className="border-b bg-white text-[11px] uppercase tracking-wide text-neutral-500">
                                              <th className="px-2 py-1 text-left">Item Name & Description</th>
                                              <th className="px-2 py-1 text-left">HSN</th>
                                              <th className="px-2 py-1 text-right">Qty</th>
                                              <th className="px-2 py-1 text-right">Amount</th>
                                              <th className="px-2 py-1 text-right">Tax %</th>
                                              <th className="px-2 py-1 text-right">CGST</th>
                                              <th className="px-2 py-1 text-right">SGST</th>
                                              <th className="px-2 py-1 text-right">IGST</th>
                                              <th className="px-2 py-1 text-right">UGST</th>
                                              <th className="px-2 py-1 text-right">Total Tax</th>
                                            </tr>
                                          </thead>
                                          <tbody>
                                            {detailRows.map((detail) => (
                                              <tr key={`${detail.sales_invoice_no}-${detail.s_no}`} className="border-b border-neutral-100">
                                                <td className="px-2 py-1 text-left">{detail.item_name_description || '-'}</td>
                                                <td className="px-2 py-1 text-left">{detail.hsn || '-'}</td>
                                                <td className="px-2 py-1 text-right">{formatQuantity(detail.quantity)}</td>
                                                <td className="px-2 py-1 text-right">{formatDecimalAmount(detail.invoice_amount)}</td>
                                                <td className="px-2 py-1 text-right">{formatTaxPercent(detail.tax_percent)}</td>
                                                <td className="px-2 py-1 text-right">{formatDecimalAmount(detail.cgst_amount)}</td>
                                                <td className="px-2 py-1 text-right">{formatDecimalAmount(detail.sgst_amount)}</td>
                                                <td className="px-2 py-1 text-right">{formatDecimalAmount(detail.igst_amount)}</td>
                                                <td className="px-2 py-1 text-right">{formatDecimalAmount(detail.ugst_amount)}</td>
                                                <td className="px-2 py-1 text-right font-semibold">{formatDecimalAmount(detail.total_tax_amount)}</td>
                                              </tr>
                                            ))}
                                          </tbody>
                                        </table>
                                      </div>
                                    )}
                                  </td>
                                </tr>
                              )}
                            </Fragment>
                          );
                        })
                      )}

                      {gstData.items.length > 0 && (
                        <tr className="bg-neutral-100 font-semibold text-neutral-800">
                          <td colSpan={7} className="px-3 py-3 text-right">Sub Total</td>
                          <td className="px-3 py-3 text-right">{formatDecimalAmount(gstData.subtotal.invoice_amount)}</td>
                          <td className="px-3 py-3 text-center">-</td>
                          <td className="px-3 py-3 text-right">-</td>
                          <td className="px-3 py-3 text-right">{formatDecimalAmount(gstData.subtotal.cgst_amount)}</td>
                          <td className="px-3 py-3 text-right">{formatDecimalAmount(gstData.subtotal.sgst_amount)}</td>
                          <td className="px-3 py-3 text-right">{formatDecimalAmount(gstData.subtotal.igst_amount)}</td>
                          <td className="px-3 py-3 text-right">{formatDecimalAmount(gstData.subtotal.ugst_amount)}</td>
                          <td className="px-3 py-3 text-right">{formatDecimalAmount(gstData.subtotal.export_amount)}</td>
                          <td className="px-3 py-3 text-right">{formatDecimalAmount(gstData.subtotal.total_tax_amount)}</td>
                          <td className="px-3 py-3 text-center">-</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                <div className="grid grid-cols-2 gap-4 border-t border-neutral-200 bg-white p-4 md:grid-cols-4">
                  <div>
                    <p className="text-xs text-neutral-500">Taxable Value</p>
                    <p className="text-sm font-bold text-neutral-800">{formatAmount(gstData.summary.total_taxable)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-neutral-500">CGST</p>
                    <p className="text-sm font-bold text-neutral-800">{formatAmount(gstData.summary.total_cgst)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-neutral-500">SGST</p>
                    <p className="text-sm font-bold text-neutral-800">{formatAmount(gstData.summary.total_sgst)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-neutral-500">IGST</p>
                    <p className="text-sm font-bold text-neutral-800">{formatAmount(gstData.summary.total_igst)}</p>
                  </div>
                </div>
              </div>
            )}
            {gstr2Data && (
              <div className="hms-card overflow-hidden">
                <div className="border-b border-neutral-200 bg-neutral-50 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h3 className="text-sm font-bold text-neutral-800">{gstr2Data.report_title}</h3>
                    <div className="flex items-center gap-2">
                      <button type="button" onClick={() => handleGstr2Export('xlsx')} className="rounded border border-neutral-300 bg-white px-3 py-1 text-xs font-semibold text-neutral-700 hover:bg-neutral-100">Export XLSX</button>
                      <button type="button" onClick={() => handleGstr2Export('pdf')} className="rounded border border-neutral-300 bg-white px-3 py-1 text-xs font-semibold text-neutral-700 hover:bg-neutral-100">Export PDF</button>
                    </div>
                  </div>
                  <p className="mt-1 text-xs text-neutral-600">
                    Period: {gstr2Data.from_date_display || fromDate} to {gstr2Data.to_date_display || toDate} | Frequency: {gstr2Data.frequency_label} | Rows: {gstr2Data.count}
                  </p>
                  {!!gstr2Data.validation_error_count && gstr2Data.validation_error_count > 0 && (
                    <div className="mt-2 rounded border border-amber-300 bg-amber-50 px-2 py-2 text-xs text-amber-800">
                      <p>Validation warnings: {gstr2Data.validation_error_count}. All records are included in totals; review highlighted issues.</p>
                      {gstr2Data.problematic_records && gstr2Data.problematic_records.length > 0 && (
                        <ul className="mt-1 list-disc pl-4">
                          {gstr2Data.problematic_records.slice(0, 5).map((record) => (
                            <li key={`gstr2-${record.document_no}-${record.document_date || 'na'}`}>
                              {record.document_type.toUpperCase()} {record.document_no || '(missing number)'}: {(record.errors || []).slice(0, 2).join(' | ')}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-neutral-100 text-xs uppercase tracking-wide text-neutral-600">
                        <th className="px-3 py-2 text-left">S.No</th>
                        <th className="px-3 py-2 text-left">GRN Date</th>
                        <th className="px-3 py-2 text-left">GRN No</th>
                        <th className="px-3 py-2 text-left">Name of the Supplier</th>
                        <th className="px-3 py-2 text-left">Supplier GSTIN No</th>
                        <th className="px-3 py-2 text-left">Business Place</th>
                        <th className="px-3 py-2 text-left">Place of Supply</th>
                        <th className="px-3 py-2 text-right">GRN Amount</th>
                        <th className="px-3 py-2 text-center">Currency</th>
                        <th className="px-3 py-2 text-right">Tax %</th>
                        <th className="px-3 py-2 text-right">CGST Amount</th>
                        <th className="px-3 py-2 text-right">SGST Amount</th>
                        <th className="px-3 py-2 text-right">IGST Amount</th>
                        <th className="px-3 py-2 text-right">UGST Amount</th>
                        <th className="px-3 py-2 text-right">Import</th>
                        <th className="px-3 py-2 text-right">Total Tax Amount</th>
                        <th className="px-3 py-2 text-center">Details</th>
                      </tr>
                    </thead>
                    <tbody>
                      {gstr2Data.items.length === 0 ? (
                        <tr>
                          <td colSpan={17} className="px-4 py-6 text-center text-neutral-500">
                            No purchase transactions found for selected filters.
                          </td>
                        </tr>
                      ) : (
                        gstr2Data.items.map((row) => {
                          const detailRows = gstr2DetailMap.get(row.grn_no) || [];
                          const isExpanded = Boolean(expandedGstr2Grns[row.grn_no]);
                          return (
                            <Fragment key={`${row.grn_no}-${row.s_no}`}>
                              <tr className="border-b border-neutral-100">
                                <td className="px-3 py-2 text-left">{row.s_no}</td>
                                <td className="px-3 py-2 text-left">{row.grn_date || '-'}</td>
                                <td className="px-3 py-2 text-left">{row.grn_no}</td>
                                <td className="px-3 py-2 text-left">{row.supplier_name}</td>
                                <td className="px-3 py-2 text-left font-mono text-xs break-all">{row.supplier_gstin_no}</td>
                                <td className="px-3 py-2 text-left">{row.business_place}</td>
                                <td className="px-3 py-2 text-left">{row.place_of_supply}</td>
                                <td className="px-3 py-2 text-right">{formatDecimalAmount(row.grn_amount)}</td>
                                <td className="px-3 py-2 text-center">{row.currency}</td>
                                <td className="px-3 py-2 text-right">{formatTaxPercent(row.tax_percent)}</td>
                                <td className="px-3 py-2 text-right">{formatDecimalAmount(row.cgst_amount)}</td>
                                <td className="px-3 py-2 text-right">{formatDecimalAmount(row.sgst_amount)}</td>
                                <td className="px-3 py-2 text-right">{formatDecimalAmount(row.igst_amount)}</td>
                                <td className="px-3 py-2 text-right">{formatDecimalAmount(row.ugst_amount)}</td>
                                <td className="px-3 py-2 text-right">{formatDecimalAmount(row.import_amount)}</td>
                                <td className="px-3 py-2 text-right font-semibold">{formatDecimalAmount(row.total_tax_amount)}</td>
                                <td className="px-3 py-2 text-center">
                                  <button
                                    type="button"
                                    onClick={() => toggleGstr2Details(row.grn_no)}
                                    className="rounded border border-neutral-300 bg-white px-2 py-1 text-xs font-semibold text-neutral-700 hover:bg-neutral-100"
                                  >
                                    {isExpanded ? 'Hide Details' : 'View Details'}
                                  </button>
                                </td>
                              </tr>
                              {isExpanded && (
                                <tr className="bg-neutral-50">
                                  <td colSpan={17} className="px-3 py-3">
                                    {detailRows.length === 0 ? (
                                      <div className="text-xs text-neutral-500">No product details available for this GRN.</div>
                                    ) : (
                                      <div className="overflow-x-auto">
                                        <table className="w-full text-xs">
                                          <thead>
                                            <tr className="border-b bg-white text-[11px] uppercase tracking-wide text-neutral-500">
                                              <th className="px-2 py-1 text-left">Item Name & Description</th>
                                              <th className="px-2 py-1 text-left">HSN</th>
                                              <th className="px-2 py-1 text-right">Qty</th>
                                              <th className="px-2 py-1 text-right">Amount</th>
                                              <th className="px-2 py-1 text-right">Tax %</th>
                                              <th className="px-2 py-1 text-right">CGST</th>
                                              <th className="px-2 py-1 text-right">SGST</th>
                                              <th className="px-2 py-1 text-right">IGST</th>
                                              <th className="px-2 py-1 text-right">UGST</th>
                                              <th className="px-2 py-1 text-right">Total Tax</th>
                                            </tr>
                                          </thead>
                                          <tbody>
                                            {detailRows.map((detail) => (
                                              <tr key={`${detail.grn_no}-${detail.s_no}`} className="border-b border-neutral-100">
                                                <td className="px-2 py-1 text-left">{detail.item_name_description || '-'}</td>
                                                <td className="px-2 py-1 text-left">{detail.hsn || '-'}</td>
                                                <td className="px-2 py-1 text-right">{formatQuantity(detail.quantity)}</td>
                                                <td className="px-2 py-1 text-right">{formatDecimalAmount(detail.grn_amount)}</td>
                                                <td className="px-2 py-1 text-right">{formatTaxPercent(detail.tax_percent)}</td>
                                                <td className="px-2 py-1 text-right">{formatDecimalAmount(detail.cgst_amount)}</td>
                                                <td className="px-2 py-1 text-right">{formatDecimalAmount(detail.sgst_amount)}</td>
                                                <td className="px-2 py-1 text-right">{formatDecimalAmount(detail.igst_amount)}</td>
                                                <td className="px-2 py-1 text-right">{formatDecimalAmount(detail.ugst_amount)}</td>
                                                <td className="px-2 py-1 text-right font-semibold">{formatDecimalAmount(detail.total_tax_amount)}</td>
                                              </tr>
                                            ))}
                                          </tbody>
                                        </table>
                                      </div>
                                    )}
                                  </td>
                                </tr>
                              )}
                            </Fragment>
                          );
                        })
                      )}

                      {gstr2Data.items.length > 0 && (
                        <tr className="bg-neutral-100 font-semibold text-neutral-800">
                          <td colSpan={7} className="px-3 py-3 text-right">Sub Total</td>
                          <td className="px-3 py-3 text-right">{formatDecimalAmount(gstr2Data.subtotal.grn_amount)}</td>
                          <td className="px-3 py-3 text-center">-</td>
                          <td className="px-3 py-3 text-right">-</td>
                          <td className="px-3 py-3 text-right">{formatDecimalAmount(gstr2Data.subtotal.cgst_amount)}</td>
                          <td className="px-3 py-3 text-right">{formatDecimalAmount(gstr2Data.subtotal.sgst_amount)}</td>
                          <td className="px-3 py-3 text-right">{formatDecimalAmount(gstr2Data.subtotal.igst_amount)}</td>
                          <td className="px-3 py-3 text-right">{formatDecimalAmount(gstr2Data.subtotal.ugst_amount)}</td>
                          <td className="px-3 py-3 text-right">{formatDecimalAmount(gstr2Data.subtotal.import_amount)}</td>
                          <td className="px-3 py-3 text-right">{formatDecimalAmount(gstr2Data.subtotal.total_tax_amount)}</td>
                          <td className="px-3 py-3 text-center">-</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                <div className="grid grid-cols-2 gap-4 border-t border-neutral-200 bg-white p-4 md:grid-cols-4">
                  <div>
                    <p className="text-xs text-neutral-500">Taxable Value</p>
                    <p className="text-sm font-bold text-neutral-800">{formatAmount(gstr2Data.summary.total_taxable)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-neutral-500">CGST</p>
                    <p className="text-sm font-bold text-neutral-800">{formatAmount(gstr2Data.summary.total_cgst)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-neutral-500">SGST</p>
                    <p className="text-sm font-bold text-neutral-800">{formatAmount(gstr2Data.summary.total_sgst)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-neutral-500">IGST</p>
                    <p className="text-sm font-bold text-neutral-800">{formatAmount(gstr2Data.summary.total_igst)}</p>
                  </div>
                </div>
              </div>
            )}
            {gstReconciliationData && (
              <div className="hms-card overflow-hidden">
                <div className="border-b border-neutral-200 bg-neutral-50 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h3 className="text-sm font-bold text-neutral-800">{gstReconciliationData.report_title}</h3>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => handleReconciliationExport('xlsx')}
                        className="rounded border border-neutral-300 bg-white px-3 py-1 text-xs font-semibold text-neutral-700 hover:bg-neutral-100"
                      >
                        Export XLSX
                      </button>
                      <button
                        type="button"
                        onClick={() => handleReconciliationExport('pdf')}
                        className="rounded border border-neutral-300 bg-white px-3 py-1 text-xs font-semibold text-neutral-700 hover:bg-neutral-100"
                      >
                        Export PDF
                      </button>
                    </div>
                  </div>
                  <p className="mt-1 text-xs text-neutral-600">
                    Period: {gstReconciliationData.from_date_display || fromDate} to {gstReconciliationData.to_date_display || toDate} | Frequency: {gstReconciliationData.frequency_label} | Rows: {gstReconciliationData.count}
                  </p>
                  {!!gstReconciliationData.validation_error_count && gstReconciliationData.validation_error_count > 0 && (
                    <div className="mt-2 rounded border border-amber-300 bg-amber-50 px-2 py-2 text-xs text-amber-800">
                      <p>Validation warnings: {gstReconciliationData.validation_error_count}. Reconciliation includes all source rows; review highlighted issues.</p>
                      {gstReconciliationData.problematic_records && gstReconciliationData.problematic_records.length > 0 && (
                        <ul className="mt-1 list-disc pl-4">
                          {gstReconciliationData.problematic_records.slice(0, 5).map((record) => (
                            <li key={`recon-${record.document_no}-${record.document_date || 'na'}`}>
                              {record.document_type.toUpperCase()} {record.document_no || '(missing number)'}: {(record.errors || []).slice(0, 2).join(' | ')}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-neutral-100 text-xs uppercase tracking-wide text-neutral-600">
                        <th className="px-3 py-2 text-left">S.No</th>
                        <th className="px-3 py-2 text-left">Tax Type</th>
                        <th className="px-3 py-2 text-left">Date</th>
                        <th className="px-3 py-2 text-left">Partner</th>
                        <th className="px-3 py-2 text-left">GSTIN</th>
                        <th className="px-3 py-2 text-left">Business Place</th>
                        <th className="px-3 py-2 text-left">Place of Supply</th>
                        <th className="px-3 py-2 text-right">Amount</th>
                        <th className="px-3 py-2 text-center">Currency</th>
                        <th className="px-3 py-2 text-right">Tax %</th>
                        <th className="px-3 py-2 text-right">CGST</th>
                        <th className="px-3 py-2 text-right">SGST</th>
                        <th className="px-3 py-2 text-right">IGST</th>
                        <th className="px-3 py-2 text-right">UGST</th>
                        <th className="px-3 py-2 text-right">Import/Export</th>
                        <th className="px-3 py-2 text-right">Total Tax</th>
                      </tr>
                    </thead>
                    <tbody>
                      {gstReconciliationData.items.length === 0 ? (
                        <tr>
                          <td colSpan={16} className="px-4 py-6 text-center text-neutral-500">
                            No GST transactions found for selected filters.
                          </td>
                        </tr>
                      ) : (
                        gstReconciliationData.items.map((row) => (
                          <tr key={`${row.tax_type}-${row.s_no}`} className="border-b border-neutral-100">
                            <td className="px-3 py-2 text-left">{row.s_no}</td>
                            <td className="px-3 py-2 text-left">{row.tax_type}</td>
                            <td className="px-3 py-2 text-left">{row.date || '-'}</td>
                            <td className="px-3 py-2 text-left">{row.name_of_partner}</td>
                            <td className="px-3 py-2 text-left font-mono text-xs break-all">{row.partner_gstin_no}</td>
                            <td className="px-3 py-2 text-left">{row.business_place}</td>
                            <td className="px-3 py-2 text-left">{row.place_of_supply}</td>
                            <td className="px-3 py-2 text-right">{formatDecimalAmount(row.grn_or_invoice_amount)}</td>
                            <td className="px-3 py-2 text-center">{row.currency}</td>
                            <td className="px-3 py-2 text-right">{formatTaxPercent(row.tax_percent)}</td>
                            <td className="px-3 py-2 text-right">{formatDecimalAmount(row.cgst_amount)}</td>
                            <td className="px-3 py-2 text-right">{formatDecimalAmount(row.sgst_amount)}</td>
                            <td className="px-3 py-2 text-right">{formatDecimalAmount(row.igst_amount)}</td>
                            <td className="px-3 py-2 text-right">{formatDecimalAmount(row.ugst_amount)}</td>
                            <td className="px-3 py-2 text-right">{formatDecimalAmount(row.import_export_amount)}</td>
                            <td className="px-3 py-2 text-right font-semibold">{formatDecimalAmount(row.total_tax_amount)}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>

                <div className="grid grid-cols-1 gap-3 border-t border-neutral-200 bg-white p-4 md:grid-cols-3">
                  <div className="rounded border border-green-200 bg-green-50 p-3">
                    <p className="text-xs font-semibold text-green-700">Sub Total (Input Tax)</p>
                    <p className="mt-1 text-xs text-green-800">CGST: {formatDecimalAmount(gstReconciliationData.subtotal_input_tax.cgst_amount)}</p>
                    <p className="text-xs text-green-800">SGST: {formatDecimalAmount(gstReconciliationData.subtotal_input_tax.sgst_amount)}</p>
                    <p className="text-xs text-green-800">IGST: {formatDecimalAmount(gstReconciliationData.subtotal_input_tax.igst_amount)}</p>
                    <p className="text-xs text-green-800">UGST: {formatDecimalAmount(gstReconciliationData.subtotal_input_tax.ugst_amount)}</p>
                    <p className="text-xs text-green-800">Import/Export: {formatDecimalAmount(gstReconciliationData.subtotal_input_tax.import_export_amount)}</p>
                    <p className="mt-1 text-sm font-bold text-green-900">Total Tax: {formatDecimalAmount(gstReconciliationData.subtotal_input_tax.total_tax_amount)}</p>
                  </div>
                  <div className="rounded border border-blue-200 bg-blue-50 p-3">
                    <p className="text-xs font-semibold text-blue-700">Sub Total (Output Tax)</p>
                    <p className="mt-1 text-xs text-blue-800">CGST: {formatDecimalAmount(gstReconciliationData.subtotal_output_tax.cgst_amount)}</p>
                    <p className="text-xs text-blue-800">SGST: {formatDecimalAmount(gstReconciliationData.subtotal_output_tax.sgst_amount)}</p>
                    <p className="text-xs text-blue-800">IGST: {formatDecimalAmount(gstReconciliationData.subtotal_output_tax.igst_amount)}</p>
                    <p className="text-xs text-blue-800">UGST: {formatDecimalAmount(gstReconciliationData.subtotal_output_tax.ugst_amount)}</p>
                    <p className="text-xs text-blue-800">Import/Export: {formatDecimalAmount(gstReconciliationData.subtotal_output_tax.import_export_amount)}</p>
                    <p className="mt-1 text-sm font-bold text-blue-900">Total Tax: {formatDecimalAmount(gstReconciliationData.subtotal_output_tax.total_tax_amount)}</p>
                  </div>
                  <div className="rounded border border-amber-200 bg-amber-50 p-3">
                    <p className="text-xs font-semibold text-amber-700">Difference (Output - Input)</p>
                    <p className="mt-1 text-xs text-amber-800">CGST: {formatDecimalAmount(gstReconciliationData.difference_amount.cgst_amount)}</p>
                    <p className="text-xs text-amber-800">SGST: {formatDecimalAmount(gstReconciliationData.difference_amount.sgst_amount)}</p>
                    <p className="text-xs text-amber-800">IGST: {formatDecimalAmount(gstReconciliationData.difference_amount.igst_amount)}</p>
                    <p className="text-xs text-amber-800">UGST: {formatDecimalAmount(gstReconciliationData.difference_amount.ugst_amount)}</p>
                    <p className="text-xs text-amber-800">Import/Export: {formatDecimalAmount(gstReconciliationData.difference_amount.import_export_amount)}</p>
                    <p className="mt-1 text-sm font-bold text-amber-900">Net Tax: {formatDecimalAmount(gstReconciliationData.difference_amount.total_tax_amount)}</p>
                  </div>
                </div>
              </div>
            )}
            {gstr3bData && (
              <div className="hms-card p-6">
                <h3 className="mb-4 text-sm font-bold text-neutral-700">GSTR-3B Summary (Tax Liability)</h3>
                <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                  <div className="rounded-lg bg-blue-50 p-4"><p className="text-xs text-blue-600">Output Tax</p><p className="text-xl font-bold text-blue-800">{formatAmount(gstr3bData.output_tax)}</p></div>
                  <div className="rounded-lg bg-green-50 p-4"><p className="text-xs text-green-600">Input Tax Credit (ITC)</p><p className="text-xl font-bold text-green-800">{formatAmount(gstr3bData.itc)}</p></div>
                  <div className="rounded-lg bg-amber-50 p-4"><p className="text-xs text-amber-600">Net Tax Payable</p><p className="text-xl font-bold text-amber-800">{formatAmount(gstr3bData.net_tax_payable)}</p></div>
                </div>
              </div>
            )}
            {gstAuditTrail && (
              <div className="hms-card overflow-hidden">
                <div className="border-b border-neutral-200 bg-neutral-50 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h3 className="text-sm font-bold text-neutral-800">{gstAuditTrail.report_title}</h3>
                    <div className="flex items-center gap-2">
                      <label htmlFor="gst-audit-report-type" className="text-xs font-medium text-neutral-600">Report</label>
                      <select
                        id="gst-audit-report-type"
                        value={auditReportType}
                        onChange={(e) => handleAuditReportTypeChange(e.target.value as 'all' | 'gstr1' | 'gstr2' | 'gstr3b' | 'reconciliation')}
                        className="rounded border border-neutral-300 bg-white px-2 py-1 text-xs text-neutral-700"
                      >
                        <option value="all">All</option>
                        <option value="gstr1">GSTR-1</option>
                        <option value="gstr2">GSTR-2</option>
                        <option value="gstr3b">GSTR-3B</option>
                        <option value="reconciliation">Reconciliation</option>
                      </select>
                      <label htmlFor="gst-audit-page-size" className="text-xs font-medium text-neutral-600">Rows</label>
                      <select
                        id="gst-audit-page-size"
                        value={auditPageSize}
                        onChange={(e) => handleAuditPageSizeChange(Number(e.target.value))}
                        className="rounded border border-neutral-300 bg-white px-2 py-1 text-xs text-neutral-700"
                      >
                        <option value={10}>10</option>
                        <option value={20}>20</option>
                        <option value={50}>50</option>
                      </select>
                    </div>
                  </div>
                  <p className="mt-1 text-xs text-neutral-600">
                    Period: {gstAuditTrail.from_date_display || fromDate} to {gstAuditTrail.to_date_display || toDate} | Total Events: {gstAuditTrail.total}
                  </p>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-neutral-100 text-xs uppercase tracking-wide text-neutral-600">
                        <th className="px-3 py-2 text-left">Timestamp</th>
                        <th className="px-3 py-2 text-left">Action</th>
                        <th className="px-3 py-2 text-left">Report Type</th>
                        <th className="px-3 py-2 text-left">Status</th>
                        <th className="px-3 py-2 text-left">Range</th>
                        <th className="px-3 py-2 text-left">Frequency</th>
                        <th className="px-3 py-2 text-left">User</th>
                      </tr>
                    </thead>
                    <tbody>
                      {gstAuditTrail.items.length === 0 ? (
                        <tr>
                          <td colSpan={7} className="px-4 py-6 text-center text-neutral-500">
                            No audit records found for selected filters.
                          </td>
                        </tr>
                      ) : (
                        gstAuditTrail.items.map((item) => (
                          <tr key={item.id} className="border-b border-neutral-100">
                            <td className="px-3 py-2 text-left">{formatAuditTimestamp(item.timestamp)}</td>
                            <td className="px-3 py-2 text-left">{item.action}</td>
                            <td className="px-3 py-2 text-left">{item.report_type}</td>
                            <td className="px-3 py-2 text-left">{item.status}</td>
                            <td className="px-3 py-2 text-left">{item.start_date && item.end_date ? `${item.start_date} to ${item.end_date}` : '-'}</td>
                            <td className="px-3 py-2 text-left">{item.frequency || '-'}</td>
                            <td className="px-3 py-2 text-left">{item.user_name || item.user_id || '-'}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
                {gstAuditTrail.total_pages > 1 && (
                  <div className="flex items-center justify-between border-t border-neutral-200 bg-white px-4 py-3 text-xs text-neutral-600">
                    <span>Page {gstAuditTrail.page} of {gstAuditTrail.total_pages}</span>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        disabled={gstAuditTrail.page <= 1}
                        onClick={() => setAuditPage((prev) => Math.max(1, prev - 1))}
                        className="rounded border border-neutral-300 bg-white px-3 py-1 font-semibold text-neutral-700 hover:bg-neutral-100 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Previous
                      </button>
                      <button
                        type="button"
                        disabled={gstAuditTrail.page >= gstAuditTrail.total_pages}
                        onClick={() => setAuditPage((prev) => prev + 1)}
                        className="rounded border border-neutral-300 bg-white px-3 py-1 font-semibold text-neutral-700 hover:bg-neutral-100 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Next
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* P&L Tab */}
        {!loading && activeTab === 'pl' && (
          <div className="space-y-6">
            {!plData ? (
              <div className="hms-card px-5 py-4 text-sm text-neutral-600">
                Profit & Loss data is unavailable for the selected range. Expand the date range to include sales and purchases.
              </div>
            ) : (
              <>
                <div className="hms-card p-6">
                  <h3 className="mb-6 text-sm font-bold text-neutral-700">Profit & Loss Statement</h3>
                  <div className="space-y-4">
                    <div className="flex items-center justify-between border-b pb-3">
                      <span className="text-sm font-semibold text-neutral-600">Net Sales</span>
                      <span className="text-lg font-bold text-green-600">{formatAmount(plData.net_sales)}</span>
                    </div>
                    <div className="flex items-center justify-between border-b pb-3">
                      <span className="text-sm font-semibold text-neutral-600">Less: Purchases</span>
                      <span className="text-lg font-bold text-red-600">({formatAmount(plData.purchases)})</span>
                    </div>
                    <div className="flex items-center justify-between border-b-2 border-primary/20 pb-3">
                      <span className="text-sm font-bold text-primary">Gross Profit</span>
                      <span className={`text-xl font-bold ${plData.gross_profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>{formatAmount(plData.gross_profit)}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-neutral-500">Gross Profit Margin</span>
                      <span className="text-lg font-bold text-primary">{plData.gross_profit_margin_percent}%</span>
                    </div>
                  </div>
                </div>

                {/* P&L Visual */}
                <div className="hms-card p-6">
                  <h3 className="mb-4 text-sm font-bold text-neutral-700">Revenue vs Purchases</h3>
                  <ResponsiveContainer width="100%" height={250}>
                    <BarChart data={[{ name: 'Sales', value: plData.net_sales }, { name: 'Purchases', value: plData.purchases }, { name: 'Profit', value: plData.gross_profit }]}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                      <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                      <YAxis tick={{ fontSize: 12 }} tickFormatter={v => `₹${(v/100/1000).toFixed(0)}K`} />
                      <Tooltip formatter={(v: number) => formatAmount(v)} />
                      <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                        {[0, 1, 2].map(idx => <Cell key={idx} fill={['#22c55e', '#ef4444', '#1E3A5F'][idx]} />)}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </AppLayout>
  );
};

export default ReportsPage;

