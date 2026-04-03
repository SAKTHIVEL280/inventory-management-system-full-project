/**
 * Sales API Client
 * 
 * Handles all sales workflow operations:
 * - Quotations
 * - Sales Orders (SO)
 * - Sales Invoices
 * - Sales Returns
 */

import { apiClient } from './client';

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

export interface ConvertQuotationToSOPayload {
  sold_to_customer_id?: string;
  bill_to_customer_id?: string;
  ship_to_customer_id?: string;
  expected_delivery_date?: string;
}

export interface CreateSalesOrderPayload {
  customer_id: string;
  quotation_id?: string;
  order_date: string;
  expected_delivery_date?: string;
  sold_to_customer_id?: string;
  bill_to_customer_id?: string;
  ship_to_customer_id?: string;
  notes?: string;
  terms_conditions?: string;
  status?: string;
  currency_code?: string;
  exchange_rate?: number;
  items: SalesLineItem[];
}

export interface UpdateSalesOrderPayload extends Partial<CreateSalesOrderPayload> {}

export interface UpdateSalesOrderStatusPayload {
  status: string;
}

export interface CreateInvoicePayload {
  customer_id: string;
  sales_order_id?: string;
  quotation_id?: string;
  invoice_date: string;
  due_date?: string;
  sold_to_customer_id?: string;
  bill_to_customer_id?: string;
  ship_to_customer_id?: string;
  supply_state?: string;
  supply_state_code?: string;
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

export interface SalesOrder {
  id: string;
  so_number: string;
  quotation_id?: string;
  customer_id: string;
  order_date: string;
  expected_delivery_date?: string;
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
  currency_code?: string;
  exchange_rate?: number;
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

export interface SalesOrderItemResponse {
  id?: string;
  product_id: string;
  description?: string;
  quantity: number;
  unit_price: number;
  discount_percent?: number;
  gst_rate: number;
  total_amount?: number;
}

export interface InvoiceDetailResponse {
  invoice: SalesInvoice;
  items: SalesInvoiceItem[];
}

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
    return apiClient.get<{ items: Quotation[]; total: number }>('/api/v1/quotations', { params });
  }

  async getQuotation(id: string) {
    return apiClient.get<Quotation>(`/api/v1/quotations/${id}`);
  }

  async createQuotation(payload: CreateQuotationPayload) {
    return apiClient.post<Quotation>('/api/v1/quotations', payload);
  }

  async updateQuotation(id: string, payload: UpdateQuotationPayload) {
    return apiClient.put<Quotation>(`/api/v1/quotations/${id}`, payload);
  }

  async updateQuotationStatus(id: string, status: string) {
    return apiClient.patch<Quotation>(`/api/v1/quotations/${id}/status`, { status });
  }

  async archiveQuotation(id: string) {
    return apiClient.patch<Quotation>(`/api/v1/quotations/${id}/archive`, {});
  }

  async restoreQuotation(id: string) {
    return apiClient.patch<Quotation>(`/api/v1/quotations/${id}/restore`, {});
  }

  async convertQuotationToSO(id: string, payload?: ConvertQuotationToSOPayload) {
    return apiClient.post<SalesOrder>(`/api/v1/quotations/${id}/convert-to-so`, payload || {});
  }

  async downloadQuotationPdf(id: string) {
    return apiClient.get(`/api/v1/quotations/${id}/pdf`, {
      responseType: 'blob',
    });
  }

  async sendQuotationEmail(id: string, email?: string) {
    return apiClient.post(`/api/v1/quotations/${id}/send-email`, { email });
  }

  // ========== Sales Orders ==========

  async listSalesOrders(
    status?: string,
    page = 1,
    page_size = 20,
    options?: { archived_only?: boolean; include_archived?: boolean }
  ) {
    const params: Record<string, string | number | boolean> = { page, page_size };
    if (status) params.status = status;
    if (options?.archived_only) params.archived_only = true;
    if (options?.include_archived) params.include_archived = true;
    return apiClient.get<{ items: SalesOrder[]; total: number }>('/api/v1/sales-orders', { params });
  }

  async getSalesOrder(id: string) {
    return apiClient.get<{ sales_order: SalesOrder; items: SalesOrderItemResponse[] }>(`/api/v1/sales-orders/${id}`);
  }

  async searchSalesOrderByNumber(soNumber: string) {
    return apiClient.get<{ sales_order: SalesOrder; items: SalesOrderItemResponse[] }>(`/api/v1/sales-orders/search/${soNumber}`);
  }

  async createSalesOrder(payload: CreateSalesOrderPayload) {
    return apiClient.post<SalesOrder>('/api/v1/sales-orders', payload);
  }

  async updateSalesOrder(id: string, payload: UpdateSalesOrderPayload) {
    return apiClient.put<SalesOrder>(`/api/v1/sales-orders/${id}`, payload);
  }

  async updateSalesOrderStatus(id: string, status: string) {
    return apiClient.patch<SalesOrder>(`/api/v1/sales-orders/${id}/status`, { status });
  }

  async archiveSalesOrder(id: string) {
    return apiClient.patch<SalesOrder>(`/api/v1/sales-orders/${id}/archive`, {});
  }

  async restoreSalesOrder(id: string) {
    return apiClient.patch<SalesOrder>(`/api/v1/sales-orders/${id}/restore`, {});
  }

  // BUG-05: Convert Sales Order to Invoice
  async convertSOToInvoice(soId: string) {
    return apiClient.post<SalesInvoice>(`/api/v1/sales-orders/${soId}/convert-to-invoice`, {});
  }

  // ========== Sales Invoices ==========

  async listInvoices(status?: string, page = 1, page_size = 20) {
    const params: Record<string, string | number> = { page, page_size };
    if (status) params.status = status;
    return apiClient.get<{ items: SalesInvoice[]; total: number }>('/api/v1/invoices', { params });
  }

  async getInvoice(id: string) {
    return apiClient.get<InvoiceDetailResponse>(`/api/v1/invoices/${id}`);
  }

  async createInvoice(payload: CreateInvoicePayload) {
    return apiClient.post<SalesInvoice>('/api/v1/invoices', payload);
  }

  async updateInvoice(id: string, payload: UpdateInvoicePayload) {
    return apiClient.put<SalesInvoice>(`/api/v1/invoices/${id}`, payload);
  }

  async issueInvoice(id: string) {
    return apiClient.post<SalesInvoice>(`/api/v1/invoices/${id}/issue`, {});
  }

  async sendInvoiceEmail(id: string, email: string) {
    return apiClient.post<{ message: string }>(`/api/v1/invoices/${id}/send-email`, { email });
  }

  // ========== Sales Returns ==========

  async listSalesReturns(page = 1, page_size = 20) {
    return apiClient.get<{ items: SalesReturn[]; total: number }>('/api/v1/sales-returns', {
      params: { page, page_size },
    });
  }

  async getSalesReturn(id: string) {
    return apiClient.get<SalesReturn>(`/api/v1/sales-returns/${id}`);
  }

  async createSalesReturn(payload: CreateSalesReturnPayload) {
    return apiClient.post<SalesReturn>('/api/v1/sales-returns', payload);
  }

  async confirmSalesReturn(id: string) {
    return apiClient.post<SalesReturn>(`/api/v1/sales-returns/${id}/confirm`, {});
  }

  async cancelSalesReturn(id: string) {
    return apiClient.post<SalesReturn>(`/api/v1/sales-returns/${id}/cancel`, {});
  }

  // ========== PDF Download ==========

  async downloadInvoicePdf(id: string) {
    return apiClient.get(`/api/v1/invoices/${id}/pdf`, {
      responseType: 'blob',
    });
  }
}

export const salesApi = new SalesApiClient();
