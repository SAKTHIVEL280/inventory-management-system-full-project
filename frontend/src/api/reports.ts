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

/**
 * Fetch dashboard statistics
 */
export const getDashboardStats = async (): Promise<DashboardStats> => {
  const response = await apiClient.get('/api/v1/reports/dashboard');
  return response.data;
};

/**
 * Fetch stock report
 */
export const getStockReport = async (lowStockOnly = false): Promise<StockReportResponse> => {
  const response = await apiClient.get('/api/v1/reports/stock', {
    params: { low_stock_only: lowStockOnly },
  });
  return response.data;
};

/**
 * Fetch sales report
 */
export const getSalesReport = async (fromDate: string, toDate: string) => {
  const response = await apiClient.get('/api/v1/reports/sales', {
    params: { from_date: fromDate, to_date: toDate },
  });
  return response.data;
};

/**
 * Fetch outstanding receivables
 */
export const getOutstandingReceivables = async () => {
  const response = await apiClient.get('/api/v1/reports/outstanding-receivables');
  return response.data;
};

/**
 * Fetch outstanding payables
 */
export const getOutstandingPayables = async () => {
  const response = await apiClient.get('/api/v1/reports/outstanding-payables');
  return response.data;
};
