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
  allocated_amount: number;
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
  status: 'pending' | 'cleared' | 'bounced' | 'cancelled';
  created_at: string;
  allocations?: any[];
}

export interface PaymentDetail {
  payment: Payment;
  allocations: PaymentAllocation[];
}

class PaymentsApiClient {
  async listPayments(options?: {
    party_type?: 'customer' | 'supplier';
    customer_id?: string;
    supplier_id?: string;
    status?: string;
    page?: number;
    page_size?: number;
  }) {
    const params: Record<string, string | number> = {
      page: options?.page ?? 1,
      page_size: options?.page_size ?? 20,
    };

    if (options?.party_type) params.party_type = options.party_type;
    if (options?.customer_id) params.customer_id = options.customer_id;
    if (options?.supplier_id) params.supplier_id = options.supplier_id;
    if (options?.status) params.status = options.status;

    return apiClient.get<{ items: Payment[]; total: number }>('/api/v1/payments', { params });
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
}

export const paymentsApi = new PaymentsApiClient();
