/**
 * Sales API Client
 * 
 * Handles all sales workflow operations:
 * - Quotations
 * - Sales Invoices
 * - Sales Returns
 */

import { apiClient } from './client';

export type InvoiceTypeValue =
  | 'export_invoice'
  | 'within_state'
  | 'other_states'
  | 'union_territory';

// Request payload types (matching backend schemas)
export interface SalesLineItem {
  product_id: string;
  description?: string;
  order_unit?: string;
  batch_no?: string;
  manufacture_date?: string;
  expiry_date?: string;
  free_quantity?: number;
  quantity: number;
  unit_price: number;
  discount_percent?: number;
  gst_rate: number;
}

export interface CreateQuotationPayload {
  customer_id: string;
  quotation_date: string;
  valid_until?: string;
  sold_to_customer_id?: string;
  bill_to_customer_id?: string;
  ship_to_customer_id?: string;
  notes?: string;
  terms_conditions?: string;
  status?: string;
  items: SalesLineItem[];
}

export interface UpdateQuotationPayload extends Partial<CreateQuotationPayload> {}

export interface UpdateQuotationStatusPayload {
  status: string;
}

export interface CreateInvoicePayload {
  customer_id: string;
  quotation_id?: string;
  invoice_date: string;
  due_date?: string;
  sold_to_customer_id?: string;
  bill_to_customer_id?: string;
  ship_to_customer_id?: string;
  supply_state?: string;
  supply_state_code?: string;
  invoice_type?: InvoiceTypeValue;
  import_export_code?: string;
  is_igst?: boolean;
  stockist_name?: string;
  stockist_city?: string;
  sales_manager_name?: string;
  notes?: string;
  terms_conditions?: string;
  // Multi-currency: exchange rate to base (INR) for foreign-currency invoices.
  // currency_code is authoritative from the customer server-side; sent for clarity.
  currency_code?: string;
  exchange_rate?: number;
  items: SalesLineItem[];
}

export interface UpdateInvoicePayload extends Partial<CreateInvoicePayload> {}

export interface SalesReturnLineItem {
  product_id: string;
  invoice_item_id?: string;
  quantity: number;
  unit_price: number;
  gst_rate: number;
}

export interface CreateSalesReturnPayload {
  invoice_id: string;
  customer_id: string;
  return_date: string;
  reason: string;
  items: SalesReturnLineItem[];
}

// Response types (from backend models)
export interface Quotation {
  id: string;
  quotation_number: string;
  customer_id: string;
  quotation_date: string;
  valid_until?: string;
  status: string;
  sold_to_customer_id?: string;
  bill_to_customer_id?: string;
  ship_to_customer_id?: string;
  subtotal: number;
  total_discount: number;
  total_taxable_amount: number;
  total_cgst: number;
  total_sgst: number;
  total_igst: number;
  total_gst: number;
  total_amount: number;
  notes?: string;
  terms_conditions?: string;
  created_at: string;
}

export interface SalesInvoice {
  id: string;
  invoice_number: string;
  sales_order_id?: string;
  quotation_id?: string;
  customer_id: string;
  // Customer name/code resolved by the API (present even for soft-deleted
  // customers, so historical invoices always show the original customer).
  customer_name?: string | null;
  customer_code?: string | null;
  invoice_date: string;
  due_date?: string;
  status: string;
  sold_to_customer_id?: string;
  bill_to_customer_id?: string;
  ship_to_customer_id?: string;
  supply_state?: string;
  supply_state_code?: string;
  invoice_type: InvoiceTypeValue;
  import_export_code?: string;
  is_igst: boolean;
  stockist_name?: string;
  stockist_city?: string;
  sales_manager_name?: string;
  subtotal: number;
  total_discount: number;
  total_taxable_amount: number;
  total_cgst: number;
  total_sgst: number;
  total_igst: number;
  total_gst: number;
  total_amount: number;
  amount_paid: number;
  amount_due: number;
  // Multi-currency: transaction currency + rate to base (INR). base_currency_total
  // is the INR equivalent of total_amount.
  currency_code?: string;
  exchange_rate?: number;
  base_currency?: string;
  base_currency_total?: number;
  pdf_url?: string;
  notes?: string;
  terms_conditions?: string;
  created_at: string;
}

export interface SalesInvoiceItem {
  id: string;
  invoice_id: string;
  product_id: string;
  description?: string;
  order_unit?: string;
  batch_no?: string;
  manufacture_date?: string;
  expiry_date?: string;
  free_quantity?: number;
  quantity: number;
  returned_quantity?: number;
  net_quantity?: number;
  unit_price: number;
  mrp?: number;
  discount_percent?: number;
  gst_rate: number;
  net_taxable_amount?: number;
  net_cgst_amount?: number;
  net_sgst_amount?: number;
  net_igst_amount?: number;
  total_amount: number;
  net_total_amount?: number;
}

export interface InvoiceBatchOption {
  batch_no: string;
  available_qty: number;
  manufacture_date?: string | null;
  expiry_date?: string | null;
}

export interface InvoiceBatchOptionsResponse {
  product_id: string;
  items: InvoiceBatchOption[];
}

export interface InvoiceDetailResponse {
  invoice: SalesInvoice;
  items: SalesInvoiceItem[];
}

type ApiCallOptions = {
  suppressGlobalErrorToast?: boolean;
};

export interface SalesReturn {
  id: string;
  return_number: string;
  invoice_id: string;
  customer_id: string;
  return_date: string;
  reason: string;
  status: string;
  subtotal: number;
  total_gst: number;
  total_amount: number;
  created_at: string;
}

class SalesApiClient {
  // ========== Quotations ==========

  async listQuotations(
    status?: string,
    page = 1,
    page_size = 20,
    options?: { archived_only?: boolean; include_archived?: boolean }
  ) {
    const params: Record<string, string | number | boolean> = { page, page_size };
    if (status) params.status = status;
    if (options?.archived_only) params.archived_only = true;
    if (options?.include_archived) params.include_archived = true;
    return apiClient.get<{ items: Quotation[]; total: number }>('/api/v2/quotations', { params });
  }

  async getQuotation(id: string) {
    return apiClient.get<Quotation>(`/api/v2/quotations/${id}`);
  }

  async createQuotation(payload: CreateQuotationPayload) {
    return apiClient.post<Quotation>('/api/v2/quotations', payload);
  }

  async updateQuotation(id: string, payload: UpdateQuotationPayload) {
    return apiClient.put<Quotation>(`/api/v2/quotations/${id}`, payload);
  }

  async updateQuotationStatus(id: string, status: string) {
    return apiClient.patch<Quotation>(`/api/v2/quotations/${id}/status`, { status });
  }

  async archiveQuotation(id: string) {
    return apiClient.patch<Quotation>(`/api/v2/quotations/${id}/archive`, {});
  }

  async restoreQuotation(id: string) {
    return apiClient.patch<Quotation>(`/api/v2/quotations/${id}/restore`, {});
  }

  async downloadQuotationPdf(id: string) {
    return apiClient.get(`/api/v2/quotations/${id}/pdf`, {
      responseType: 'blob',
    });
  }

  async sendQuotationEmail(id: string, email?: string) {
    return apiClient.post(`/api/v2/quotations/${id}/send-email`, { email });
  }

  // ========== Sales Invoices ==========

  async listInvoices(
    status?: string,
    page = 1,
    page_size = 50,
    filters?: { search?: string; date_from?: string; date_to?: string; stockist?: string[]; sales_manager?: string[] },
  ) {
    const params: Record<string, string | number | string[]> = { page, page_size };
    if (status) params.status = status;
    if (filters?.search) params.search = filters.search;
    if (filters?.date_from) params.date_from = filters.date_from;
    if (filters?.date_to) params.date_to = filters.date_to;
    if (filters?.stockist && filters.stockist.length) params.stockist = filters.stockist;
    if (filters?.sales_manager && filters.sales_manager.length) params.sales_manager = filters.sales_manager;
    return apiClient.get<{ items: SalesInvoice[]; total: number; page: number; page_size: number; has_more: boolean }>(
      '/api/v2/invoices',
      // Serialize array filters as repeated keys (stockist=a&stockist=b) so the
      // FastAPI `list[str]` query params bind correctly (default axios uses `[]`).
      { params, paramsSerializer: { indexes: null } },
    );
  }

  async getInvoice(id: string) {
    return apiClient.get<InvoiceDetailResponse>(`/api/v2/invoices/${id}`);
  }

  async getInvoiceBatchOptions(productId: string) {
    return apiClient.get<InvoiceBatchOptionsResponse>('/api/v2/invoices/batch-options', {
      params: { product_id: productId },
    });
  }

  async createInvoice(payload: CreateInvoicePayload, options?: ApiCallOptions) {
    return apiClient.post<SalesInvoice>('/api/v2/invoices', payload, {
      ...(options?.suppressGlobalErrorToast ? { skipErrorToast: true } : {}),
    } as unknown as Record<string, unknown>);
  }

  async updateInvoice(id: string, payload: UpdateInvoicePayload, options?: ApiCallOptions) {
    return apiClient.put<SalesInvoice>(`/api/v2/invoices/${id}`, payload, {
      ...(options?.suppressGlobalErrorToast ? { skipErrorToast: true } : {}),
    } as unknown as Record<string, unknown>);
  }

  async updateIssuedInvoice(id: string, payload: UpdateInvoicePayload, options?: ApiCallOptions) {
    return apiClient.put<SalesInvoice>(`/api/v2/invoices/${id}/issued-details`, payload, {
      ...(options?.suppressGlobalErrorToast ? { skipErrorToast: true } : {}),
    } as unknown as Record<string, unknown>);
  }

  async issueInvoice(id: string, options?: ApiCallOptions) {
    return apiClient.post<SalesInvoice>(`/api/v2/invoices/${id}/issue`, {}, {
      ...(options?.suppressGlobalErrorToast ? { skipErrorToast: true } : {}),
    } as unknown as Record<string, unknown>);
  }

  async sendInvoiceEmail(id: string, email: string) {
    return apiClient.post<{ message: string }>(`/api/v2/invoices/${id}/send-email`, { email });
  }

  // ========== Sales Returns ==========

  async listSalesReturns(page = 1, page_size = 20) {
    return apiClient.get<{ items: SalesReturn[]; total: number }>('/api/v2/sales-returns', {
      params: { page, page_size },
    });
  }

  async getSalesReturn(id: string) {
    return apiClient.get<SalesReturn>(`/api/v2/sales-returns/${id}`);
  }

  async createSalesReturn(payload: CreateSalesReturnPayload) {
    return apiClient.post<SalesReturn>('/api/v2/sales-returns', payload);
  }

  async confirmSalesReturn(id: string) {
    return apiClient.post<SalesReturn>(`/api/v2/sales-returns/${id}/confirm`, {});
  }

  async cancelSalesReturn(id: string) {
    return apiClient.post<SalesReturn>(`/api/v2/sales-returns/${id}/cancel`, {});
  }

  // ========== PDF Download ==========

  async downloadInvoicePdf(id: string) {
    return apiClient.get(`/api/v2/invoices/${id}/pdf`, {
      responseType: 'blob',
    });
  }
}

export const salesApi = new SalesApiClient();

