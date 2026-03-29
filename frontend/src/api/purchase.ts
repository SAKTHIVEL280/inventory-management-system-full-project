/**
 * Purchase API Client
 * 
 * Handles all purchase workflow operations:
 * - Purchase Orders (PO)
 * - Goods Receipt Notes (GRN)
 * - Purchase Returns
 */

import { apiClient } from './client';

// Request payload types (matching backend schemas)
export interface PurchaseLineItem {
  id?: string;
  product_id: string;
  description?: string;
  quantity: number;
  unit_price: number;
  discount_percent?: number;
  gst_rate: number;
  purchase_order_item_id?: string;
  received_quantity?: number;
}

export interface CreatePOPayload {
  supplier_id: string;
  order_date: string;
  expected_delivery_date?: string;
  notes?: string;
  status?: string;
  currency_code?: string;
  exchange_rate?: number;
  items: PurchaseLineItem[];
}

export interface UpdatePOPayload extends Partial<CreatePOPayload> {}

export interface UpdatePOStatusPayload {
  status: string;
}

export interface CreateGRNPayload {
  supplier_id: string;
  purchase_order_id?: string;
  supplier_invoice_number?: string;
  supplier_invoice_date?: string;
  receipt_date: string;
  notes?: string;
  items: PurchaseLineItem[];
}

export interface UpdateGRNPayload extends Partial<CreateGRNPayload> {}

export interface PurchaseReturnLineItem {
  product_id: string;
  grn_item_id?: string;
  quantity: number;
  unit_price: number;
  gst_rate: number;
}

export interface CreatePurchaseReturnPayload {
  supplier_id: string;
  grn_id: string;
  return_date: string;
  reason: string;
  items: PurchaseReturnLineItem[];
}

// Response types (from backend models)
export interface PurchaseOrder {
  id: string;
  po_number: string;
  supplier_id: string;
  order_date: string;
  expected_delivery_date?: string;
  status: string;
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
  created_at: string;
  created_by?: string;
}

export interface PurchaseOrderDetail {
  purchase_order: PurchaseOrder;
  items: PurchaseLineItem[];
}

export interface GoodsReceiptNote {
  id: string;
  grn_number: string;
  purchase_order_id?: string;
  supplier_id: string;
  supplier_invoice_number?: string;
  supplier_invoice_date?: string;
  receipt_date: string;
  status: string;
  subtotal: number;
  total_discount: number;
  total_taxable_amount: number;
  total_cgst: number;
  total_sgst: number;
  total_igst: number;
  total_gst: number;
  total_amount: number;
  notes?: string;
  created_at: string;
}

export interface GRNDetail {
  grn: GoodsReceiptNote;
  items: GRNItemResponse[];
}

export interface GRNItemResponse {
  id: string;
  grn_id: string;
  product_id: string;
  purchase_order_item_id?: string;
  quantity: number;
  unit_price: number;
  discount_percent: number;
  discount_amount: number;
  taxable_amount: number;
  gst_rate: number;
  cgst_amount: number;
  sgst_amount: number;
  igst_amount: number;
  total_amount: number;
}

export interface PurchaseReturn {
  id: string;
  return_number: string;
  supplier_id: string;
  grn_id: string;
  return_date: string;
  reason: string;
  status: string;
  subtotal: number;
  total_gst: number;
  total_amount: number;
  created_at: string;
}

class PurchaseApiClient {
  // ========== Purchase Orders ==========

  async listPOs(status?: string, page = 1, page_size = 20) {
    const params: Record<string, string | number> = { page, page_size };
    if (status) params.status = status;
    return apiClient.get<{ items: PurchaseOrder[]; total: number }>('/api/v1/purchase-orders', { params });
  }

  async getPO(id: string) {
    return apiClient.get<PurchaseOrderDetail>(`/api/v1/purchase-orders/${id}`);
  }

  async createPO(payload: CreatePOPayload) {
    return apiClient.post<PurchaseOrder>('/api/v1/purchase-orders', payload);
  }

  async updatePO(id: string, payload: UpdatePOPayload) {
    return apiClient.put<PurchaseOrder>(`/api/v1/purchase-orders/${id}`, payload);
  }

  async updatePOStatus(id: string, status: string) {
    return apiClient.patch<PurchaseOrder>(`/api/v1/purchase-orders/${id}/status`, { status });
  }

  // ========== Goods Receipt Notes ==========

  async listGRNs(status?: string, page = 1, page_size = 20) {
    const params: Record<string, string | number> = { page, page_size };
    if (status) params.status = status;
    return apiClient.get<{ items: GoodsReceiptNote[]; total: number }>('/api/v1/grn', { params });
  }

  async getGRN(id: string) {
    return apiClient.get<GRNDetail>(`/api/v1/grn/${id}`);
  }

  async createGRN(payload: CreateGRNPayload) {
    return apiClient.post<GoodsReceiptNote>('/api/v1/grn', payload);
  }

  async updateGRN(id: string, payload: UpdateGRNPayload) {
    return apiClient.put<GoodsReceiptNote>(`/api/v1/grn/${id}`, payload);
  }

  async confirmGRN(id: string) {
    return apiClient.post<GoodsReceiptNote>(`/api/v1/grn/${id}/confirm`, {});
  }

  async cancelGRN(id: string) {
    return apiClient.post<GoodsReceiptNote>(`/api/v1/grn/${id}/cancel`, {});
  }

  // ========== Purchase Returns ==========

  async listPurchaseReturns(page = 1, page_size = 20) {
    return apiClient.get<{ items: PurchaseReturn[]; total: number }>('/api/v1/purchase-returns', {
      params: { page, page_size },
    });
  }

  async getPurchaseReturn(id: string) {
    return apiClient.get<PurchaseReturn>(`/api/v1/purchase-returns/${id}`);
  }

  async createPurchaseReturn(payload: CreatePurchaseReturnPayload) {
    return apiClient.post<PurchaseReturn>('/api/v1/purchase-returns', payload);
  }

  async confirmPurchaseReturn(id: string) {
    return apiClient.post<PurchaseReturn>(`/api/v1/purchase-returns/${id}/confirm`, {});
  }

  async cancelPurchaseReturn(id: string) {
    return apiClient.post<PurchaseReturn>(`/api/v1/purchase-returns/${id}/cancel`, {});
  }

  // ========== PDF Download ==========

  async downloadPOPdf(id: string) {
    return apiClient.get(`/api/v1/purchase-orders/${id}/pdf`, {
      responseType: 'blob',
    });
  }
}

export const purchaseApi = new PurchaseApiClient();
