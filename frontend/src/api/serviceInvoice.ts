import { apiClient } from './client';

// Service Invoice module (M6 ↔ BE-222). Amounts are in paise (INTEGER).
export interface ServiceInvoiceItem {
  sr_no?: number;
  item_name: string;
  description?: string | null;
  hsn_sac_code?: string | null;
  quantity: number;
  basic_price: number;
  discount_percent: number;
  discount_amount?: number;
  is_free: boolean;
  taxable_amount?: number;
  gst_rate: number;
  cgst_amount?: number;
  sgst_amount?: number;
  igst_amount?: number;
  total_amount?: number;
}

export interface ServiceInvoice {
  id: string;
  invoice_number: string;
  invoice_date: string;
  due_date: string | null;
  customer_name: string;
  customer_gstin: string | null;
  customer_email: string | null;
  customer_contact: string | null;
  billing_address: string | null;
  supply_type: string;
  subtotal: number;
  total_discount: number;
  total_taxable_amount: number;
  total_cgst: number;
  total_sgst: number;
  total_igst: number;
  total_gst: number;
  grand_total: number;
  amount_in_words: string | null;
  status: string;
  payment_status: string;
  notes: string | null;
  cancel_reason: string | null;
  items: ServiceInvoiceItem[];
}

export interface ServiceInvoicePayload {
  invoice_date: string;
  due_date?: string | null;
  customer_name: string;
  customer_gstin?: string | null;
  customer_email?: string | null;
  customer_contact?: string | null;
  billing_address?: string | null;
  customer_state_code?: string | null;
  supply_type: string;
  notes?: string | null;
  items: ServiceInvoiceItem[];
}

export interface CapStatus {
  plan: string;
  capped: boolean;
  cap: number | null;
  used_this_month: number;
  remaining: number | null;
}

const BASE = '/api/v2/service-invoices';

export const serviceInvoiceApi = {
  list: async (params: { search?: string; status?: string; date_from?: string; date_to?: string } = {}) => {
    const r = await apiClient.get<{ service_invoices: ServiceInvoice[]; count: number }>(BASE, { params });
    return r.data;
  },
  capStatus: async (): Promise<CapStatus> => {
    const r = await apiClient.get<CapStatus>(`${BASE}/cap-status`);
    return r.data;
  },
  get: async (id: string): Promise<ServiceInvoice> => {
    const r = await apiClient.get<ServiceInvoice>(`${BASE}/${id}`);
    return r.data;
  },
  create: async (payload: ServiceInvoicePayload): Promise<ServiceInvoice> => {
    const r = await apiClient.post<ServiceInvoice>(BASE, payload);
    return r.data;
  },
  update: async (id: string, payload: ServiceInvoicePayload): Promise<ServiceInvoice> => {
    const r = await apiClient.put<ServiceInvoice>(`${BASE}/${id}`, payload);
    return r.data;
  },
  issue: async (id: string) => (await apiClient.post<ServiceInvoice>(`${BASE}/${id}/issue`)).data,
  markPaid: async (id: string) => (await apiClient.post<ServiceInvoice>(`${BASE}/${id}/mark-paid`)).data,
  cancel: async (id: string, reason: string) =>
    (await apiClient.post<ServiceInvoice>(`${BASE}/${id}/cancel`, { reason })).data,
  remove: async (id: string) => {
    await apiClient.delete(`${BASE}/${id}`);
  },
  // Download as PDF (§8.4) — available on all plans incl. FREE (read access).
  downloadPdf: async (id: string, invoiceNumber: string) => {
    const r = await apiClient.get(`${BASE}/${id}/pdf`, { responseType: 'blob' });
    const url = window.URL.createObjectURL(r.data as Blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${invoiceNumber.replace(/\//g, '-')}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  },
};
