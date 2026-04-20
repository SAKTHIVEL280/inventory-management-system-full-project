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
  notes?: string;
  terms_conditions?: string;
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
  unit_price: number;
  mrp?: number;
  discount_percent?: number;
  gst_rate: number;
  total_amount: number;
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

  async listInvoices(status?: string, page = 1, page_size = 20) {
    const params: Record<string, string | number> = { page, page_size };
    if (status) params.status = status;
    return apiClient.get<{ items: SalesInvoice[]; total: number }>('/api/v2/invoices', { params });
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

