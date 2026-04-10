/**
 * Payments API Client
 * 
 * Handles all payments workflow operations:
 * - Payment recording (receipts and payments)
 * - Payment allocation to invoices
 * - Payment status management
 */

import { apiClient } from './client';

// Request payload types (matching backend schemas)
export interface PaymentAllocationRequest {
  invoice_id?: string;
  purchase_grn_id?: string;
  allocated_amount: number;
}

export interface CreatePaymentPayload {
  payment_type: 'receipt' | 'payment';
  party_type: 'customer' | 'supplier';
  customer_id?: string;
  supplier_id?: string;
  purchase_order_id?: string;
  payment_date: string;
  amount: number;
  payment_mode: string;
  reference_number?: string;
  cheque_date?: string;
  bank_name?: string;
  notes?: string;
  allocations: PaymentAllocationRequest[];
}

export interface UpdatePaymentStatusPayload {
  status: 'cleared' | 'bounced' | 'cancelled' | 'pending';
}

// Response types (from backend models)
export interface PaymentAllocation {
  id: string;
  payment_id: string;
  invoice_id?: string;
  purchase_grn_id?: string;
  purchase_order_id?: string;
  allocated_amount: number;
  invoice_number?: string;
  grn_number?: string;
  po_number?: string;
  grn_total_amount?: number;
  created_at: string;
}

export interface Payment {
  id: string;
  payment_number: string;
  payment_type: 'receipt' | 'payment';
  party_type: 'customer' | 'supplier';
  customer_id?: string;
  supplier_id?: string;
  payment_date: string;
  amount: number;
  payment_mode: string;
  reference_number?: string;
  cheque_date?: string;
  bank_name?: string;
  notes?: string;
  status: 'pending' | 'cleared' | 'bounced' | 'cancelled' | 'advance_payment_cleared' | 'full_payment_cleared';
  status_display?: string;
  purchase_order_id?: string;
  po_number?: string;
  created_at: string;
  allocations?: PaymentAllocation[];
}

export interface PaymentDetail {
  payment: Payment;
  allocations: PaymentAllocation[];
}

export interface PaymentListResponse {
  items: Payment[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

class PaymentsApiClient {
  async listPayments(options?: {
    party_type?: 'customer' | 'supplier';
    customer_id?: string;
    supplier_id?: string;
    status?: string;
    archived_only?: boolean;
    include_archived?: boolean;
    page?: number;
    page_size?: number;
  }) {
    const params: Record<string, string | number | boolean> = {
      page: options?.page ?? 1,
      page_size: options?.page_size ?? 20,
    };

    if (options?.party_type) params.party_type = options.party_type;
    if (options?.customer_id) params.customer_id = options.customer_id;
    if (options?.supplier_id) params.supplier_id = options.supplier_id;
    if (options?.status) params.status = options.status;
    if (options?.archived_only) params.archived_only = true;
    if (options?.include_archived) params.include_archived = true;

    return apiClient.get<PaymentListResponse>('/api/v1/payments', { params });
  }

  async getPayment(id: string) {
    return apiClient.get<PaymentDetail>(`/api/v1/payments/${id}`);
  }

  async createPayment(payload: CreatePaymentPayload) {
    return apiClient.post<Payment>('/api/v1/payments', payload);
  }

  async updatePaymentStatus(id: string, status: string) {
    return apiClient.patch<Payment>(`/api/v1/payments/${id}/status`, { status });
  }

  async archivePayment(id: string) {
    return apiClient.patch<Payment>(`/api/v1/payments/${id}/archive`, {});
  }

  async restorePayment(id: string) {
    return apiClient.patch<Payment>(`/api/v1/payments/${id}/restore`, {});
  }
}

export const paymentsApi = new PaymentsApiClient();
