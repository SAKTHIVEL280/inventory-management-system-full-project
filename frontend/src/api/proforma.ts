/**
 * Proforma Invoice API Client
 *
 * Independent replica of the Quotation client (api/sales.ts) renamed to
 * Proforma Invoice. Talks to /api/v2/proforma-invoices.
 */

import { apiClient } from './client';
import type { SalesLineItem } from './sales';

export interface CreateProformaInvoicePayload {
  customer_id: string;
  proforma_date: string;
  valid_until?: string;
  sold_to_customer_id?: string;
  bill_to_customer_id?: string;
  ship_to_customer_id?: string;
  notes?: string;
  terms_conditions?: string;
  status?: string;
  items: SalesLineItem[];
}

export type UpdateProformaInvoicePayload = Partial<CreateProformaInvoicePayload>;

export interface ProformaInvoice {
  id: string;
  proforma_number: string;
  customer_id: string;
  proforma_date: string;
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

class ProformaApiClient {
  async listProformaInvoices(
    status?: string,
    page = 1,
    page_size = 20,
    options?: { archived_only?: boolean; include_archived?: boolean }
  ) {
    const params: Record<string, string | number | boolean> = { page, page_size };
    if (status) params.status = status;
    if (options?.archived_only) params.archived_only = true;
    if (options?.include_archived) params.include_archived = true;
    return apiClient.get<{ items: ProformaInvoice[]; total: number }>('/api/v2/proforma-invoices', { params });
  }

  async getProformaInvoice(id: string) {
    return apiClient.get<ProformaInvoice>(`/api/v2/proforma-invoices/${id}`);
  }

  async createProformaInvoice(payload: CreateProformaInvoicePayload) {
    return apiClient.post<ProformaInvoice>('/api/v2/proforma-invoices', payload);
  }

  async updateProformaInvoice(id: string, payload: UpdateProformaInvoicePayload) {
    return apiClient.put<ProformaInvoice>(`/api/v2/proforma-invoices/${id}`, payload);
  }

  async updateProformaInvoiceStatus(id: string, status: string) {
    return apiClient.patch<ProformaInvoice>(`/api/v2/proforma-invoices/${id}/status`, { status });
  }

  async archiveProformaInvoice(id: string) {
    return apiClient.patch<ProformaInvoice>(`/api/v2/proforma-invoices/${id}/archive`, {});
  }

  async restoreProformaInvoice(id: string) {
    return apiClient.patch<ProformaInvoice>(`/api/v2/proforma-invoices/${id}/restore`, {});
  }

  async downloadProformaInvoicePdf(id: string) {
    return apiClient.get(`/api/v2/proforma-invoices/${id}/pdf`, {
      responseType: 'blob',
    });
  }

  async sendProformaInvoiceEmail(id: string, email?: string) {
    return apiClient.post(`/api/v2/proforma-invoices/${id}/send-email`, { email });
  }
}

export const proformaApi = new ProformaApiClient();
