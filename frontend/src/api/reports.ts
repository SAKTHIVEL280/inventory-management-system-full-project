/**
 * Reports API
 *
 * Dashboard statistics and reports API calls.
 */

import { apiClient } from './client';

export interface CashInFlowRow {
  customer_id: string;
  customer_name: string;
  total_received_amount: number;
  fully_settled_amount: number;
  partially_settled_amount: number;
}

export interface CashInFlowSummary {
  total_received_amount: number;
  fully_settled_amount: number;
  partially_settled_amount: number;
}

export interface DashboardStats {
  total_products: number;
  total_customers: number;
  total_suppliers: number;
  low_stock_count: number;
  safety_stock_count: number;
  pending_purchase_orders: number;
  pending_sales_orders: number;
  today_sales: number;
  month_sales: number;
  outstanding_receivables: number;
  outstanding_payables: number;
  overdue_invoices_count: number;
  sales_trend: { date: string; amount: number }[];
  top_products: { product_name: string; quantity_sold: number; amount: number }[];
  cash_in_flow: {
    daily: CashInFlowRow[];
    weekly: CashInFlowRow[];
    monthly: CashInFlowRow[];
  };
  cash_in_flow_summary: {
    daily: CashInFlowSummary;
    weekly: CashInFlowSummary;
    monthly: CashInFlowSummary;
  };
  recent_invoices: { invoice_number: string; customer_name: string; amount: number; status: string; date: string }[];
}

export interface StockReportItem {
  product_code: string;
  product_name: string;
  hsn: string;
  batch_no: string | null;
  manufacture_date: string | null;
  expiry_date: string | null;
  closing_qty: number;
  min_stock: number;
  safety_stock: number;
  status: string;
}

export interface StockReportResponse {
  items: StockReportItem[];
  total: number;
}

export interface GSTR1ReportRow {
  s_no: number;
  sales_invoice_date: string | null;
  sales_invoice_no: string;
  bill_to_party_name: string;
  bill_to_party_gstin_no: string;
  place_of_supply: string;
  ship_to_party_name: string;
  invoice_amount: number;
  currency: string;
  tax_percent: number | null;
  cgst_amount: number;
  sgst_amount: number;
  igst_amount: number;
  ugst_amount: number;
  export_amount: number;
  total_tax_amount: number;
}

export interface GSTR1Subtotal {
  invoice_amount: number;
  cgst_amount: number;
  sgst_amount: number;
  igst_amount: number;
  ugst_amount: number;
  export_amount: number;
  total_tax_amount: number;
}

export interface GSTProblematicRecord {
  document_type: string;
  document_no: string;
  document_date: string | null;
  errors: string[];
}

export interface GSTR1ReportResponse {
  report_title: string;
  frequency: 'monthly' | 'quarterly' | 'annually';
  frequency_label: string;
  from_date: string;
  to_date: string;
  from_date_display: string | null;
  to_date_display: string | null;
  summary: {
    total_taxable: number;
    total_cgst: number;
    total_sgst: number;
    total_igst: number;
  };
  count: number;
  items: GSTR1ReportRow[];
  subtotal: GSTR1Subtotal;
  strict_validation?: boolean;
  validation_error_count?: number;
  validation_errors?: string[];
  problematic_records?: GSTProblematicRecord[];
}

export interface GSTR2ReportRow {
  s_no: number;
  grn_date: string | null;
  grn_no: string;
  supplier_name: string;
  supplier_gstin_no: string;
  business_place: string;
  place_of_supply: string;
  grn_amount: number;
  currency: string;
  tax_percent: number | null;
  cgst_amount: number;
  sgst_amount: number;
  igst_amount: number;
  ugst_amount: number;
  import_amount: number;
  total_tax_amount: number;
}

export interface GSTR2Subtotal {
  grn_amount: number;
  cgst_amount: number;
  sgst_amount: number;
  igst_amount: number;
  ugst_amount: number;
  import_amount: number;
  total_tax_amount: number;
}

export interface GSTR2ReportResponse {
  report_title: string;
  frequency: 'monthly' | 'quarterly' | 'annually';
  frequency_label: string;
  from_date: string;
  to_date: string;
  from_date_display: string | null;
  to_date_display: string | null;
  summary: {
    total_taxable: number;
    total_cgst: number;
    total_sgst: number;
    total_igst: number;
  };
  count: number;
  items: GSTR2ReportRow[];
  subtotal: GSTR2Subtotal;
  strict_validation?: boolean;
  validation_error_count?: number;
  validation_errors?: string[];
  problematic_records?: GSTProblematicRecord[];
}

export interface GSTReconciliationRow {
  s_no: number;
  tax_type: 'Input Tax (Purchase)' | 'Output Tax (Sales)';
  date: string | null;
  name_of_partner: string;
  partner_gstin_no: string;
  business_place: string;
  place_of_supply: string;
  grn_or_invoice_amount: number;
  currency: string;
  tax_percent: number | null;
  cgst_amount: number;
  sgst_amount: number;
  igst_amount: number;
  ugst_amount: number;
  import_export_amount: number;
  total_tax_amount: number;
  sub_total_input_tax: number | null;
  sub_total_output_tax: number | null;
  difference_amount: number | null;
}

export interface GSTReconciliationTotals {
  transaction_amount: number;
  cgst_amount: number;
  sgst_amount: number;
  igst_amount: number;
  ugst_amount: number;
  import_export_amount: number;
  total_tax_amount: number;
}

export interface GSTReconciliationResponse {
  report_title: string;
  frequency: 'monthly' | 'quarterly' | 'annually';
  frequency_label: string;
  from_date: string;
  to_date: string;
  from_date_display: string | null;
  to_date_display: string | null;
  count: number;
  items: GSTReconciliationRow[];
  subtotal_input_tax: GSTReconciliationTotals;
  subtotal_output_tax: GSTReconciliationTotals;
  difference_amount: GSTReconciliationTotals;
  strict_validation?: boolean;
  validation_error_count?: number;
  validation_errors?: string[];
  problematic_records?: GSTProblematicRecord[];
}

export interface GSTAuditTrailItem {
  id: string;
  user_id: string | null;
  user_name: string;
  action: string;
  report_type: string;
  start_date: string | null;
  end_date: string | null;
  frequency: string;
  status: string;
  details: Record<string, unknown>;
  timestamp: string | null;
}

export interface GSTAuditTrailResponse {
  report_title: string;
  frequency: 'monthly' | 'quarterly' | 'annually';
  frequency_label: string;
  from_date: string;
  to_date: string;
  from_date_display: string | null;
  to_date_display: string | null;
  report_type: string;
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  count: number;
  items: GSTAuditTrailItem[];
}

export interface ActionLogItem {
  id: string;
  user_id: string | null;
  user_name: string;
  action: string;
  action_type: string;
  module_name: string;
  record_reference: string;
  description: string;
  status: string;
  timestamp: string | null;
  details: Record<string, unknown>;
}

export interface ActionLogsResponse {
  report_title: string;
  from_date: string;
  to_date: string;
  from_date_display: string | null;
  to_date_display: string | null;
  module: string;
  action_type: string;
  user_query: string;
  reference: string;
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  count: number;
  items: ActionLogItem[];
}

/**
 * Fetch dashboard statistics
 */
export const getDashboardStats = async (): Promise<DashboardStats> => {
  const response = await apiClient.get('/api/v2/reports/dashboard');
  return response.data;
};

/**
 * Fetch stock report
 */
export const getStockReport = async (lowStockOnly = false): Promise<StockReportResponse> => {
  const response = await apiClient.get('/api/v2/reports/stock', {
    params: { low_stock_only: lowStockOnly },
  });
  return response.data;
};

/**
 * Fetch sales report
 */
export const getSalesReport = async (fromDate: string, toDate: string) => {
  const response = await apiClient.get('/api/v2/reports/sales', {
    params: { from_date: fromDate, to_date: toDate },
  });
  return response.data;
};

/**
 * Fetch GSTR-1 report (Output Tax / Sales)
 */
export const getGSTR1Report = async (
  fromDate: string,
  toDate: string,
  frequency: 'monthly' | 'quarterly' | 'annually',
): Promise<GSTR1ReportResponse> => {
  const response = await apiClient.get('/api/v2/reports/gstr1', {
    params: { from_date: fromDate, to_date: toDate, frequency },
  });
  return response.data;
};

export const downloadGSTR1Export = async (
  fromDate: string,
  toDate: string,
  frequency: 'monthly' | 'quarterly' | 'annually',
  format: 'xlsx' | 'pdf',
): Promise<Blob> => {
  const response = await apiClient.get('/api/v2/reports/gstr1/export', {
    params: { from_date: fromDate, to_date: toDate, frequency, format },
    responseType: 'blob',
  });
  return response.data as Blob;
};

/**
 * Fetch GSTR-2 report (Input Tax / Purchase)
 */
export const getGSTR2Report = async (
  fromDate: string,
  toDate: string,
  frequency: 'monthly' | 'quarterly' | 'annually',
): Promise<GSTR2ReportResponse> => {
  const response = await apiClient.get('/api/v2/reports/gstr2', {
    params: { from_date: fromDate, to_date: toDate, frequency },
  });
  return response.data;
};

export const downloadGSTR2Export = async (
  fromDate: string,
  toDate: string,
  frequency: 'monthly' | 'quarterly' | 'annually',
  format: 'xlsx' | 'pdf',
): Promise<Blob> => {
  const response = await apiClient.get('/api/v2/reports/gstr2/export', {
    params: { from_date: fromDate, to_date: toDate, frequency, format },
    responseType: 'blob',
  });
  return response.data as Blob;
};

/**
 * Fetch GST reconciliation report (Input vs Output tax)
 */
export const getGSTReconciliationReport = async (
  fromDate: string,
  toDate: string,
  frequency: 'monthly' | 'quarterly' | 'annually',
): Promise<GSTReconciliationResponse> => {
  const response = await apiClient.get('/api/v2/reports/gst-reconciliation', {
    params: { from_date: fromDate, to_date: toDate, frequency },
  });
  return response.data;
};

/**
 * Download GST reconciliation export file
 */
export const downloadGSTReconciliationExport = async (
  fromDate: string,
  toDate: string,
  frequency: 'monthly' | 'quarterly' | 'annually',
  format: 'xlsx' | 'pdf',
): Promise<Blob> => {
  const response = await apiClient.get('/api/v2/reports/gst-reconciliation/export', {
    params: { from_date: fromDate, to_date: toDate, frequency, format },
    responseType: 'blob',
  });
  return response.data as Blob;
};

/**
 * Fetch GST audit trail records
 */
export const getGstAuditTrail = async (
  fromDate: string,
  toDate: string,
  frequency: 'monthly' | 'quarterly' | 'annually',
  reportType = 'all',
  page = 1,
  pageSize = 25,
): Promise<GSTAuditTrailResponse> => {
  const response = await apiClient.get('/api/v2/reports/gst-audit-trail', {
    params: {
      from_date: fromDate,
      to_date: toDate,
      frequency,
      report_type: reportType,
      page,
      page_size: pageSize,
    },
  });
  return response.data;
};

/**
 * Fetch system action logs
 */
export const getActionLogs = async (
  fromDate: string,
  toDate: string,
  module = 'all',
  actionType = 'all',
  userQuery = '',
  reference = '',
  page = 1,
  pageSize = 25,
): Promise<ActionLogsResponse> => {
  const response = await apiClient.get('/api/v2/reports/action-logs', {
    params: {
      from_date: fromDate,
      to_date: toDate,
      module,
      action_type: actionType,
      user_query: userQuery,
      reference,
      page,
      page_size: pageSize,
    },
  });
  return response.data;
};

/**
 * Fetch outstanding receivables
 */
export const getOutstandingReceivables = async () => {
  const response = await apiClient.get('/api/v2/reports/outstanding-receivables');
  return response.data;
};

/**
 * Fetch outstanding payables
 */
export const getOutstandingPayables = async () => {
  const response = await apiClient.get('/api/v2/reports/outstanding-payables');
  return response.data;
};

