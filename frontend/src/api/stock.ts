import { apiClient } from './client';
import { StockLedger } from '../types';

type StockAdjustmentPayload = {
  product_id: string;
  quantity: number;  // Positive for add, negative for remove
  notes?: string | null;
};

export type InventoryCountItemPayload = {
  serial_number: number;
  product_id: string;
  product_description?: string | null;
  quantity: number;
  batch_no?: string | null;
  manufacture_date?: string | null;
  expiry_date?: string | null;
};

export type InventoryCountCreatePayload = {
  count_date: string;
  count_performed_by: string;
  items: InventoryCountItemPayload[];
};

export type InventoryCountResponse = {
  id: string;
  count_number: string;
  count_date: string;
  count_performed_by: string;
  status: string;
  items: InventoryCountItemPayload[];
};

export type InventoryCountBatchOption = {
  batch_no: string;
  available_qty: number;
  manufacture_date?: string | null;
  expiry_date?: string | null;
};

export type InventoryCountBatchOptionsResponse = {
  product_id: string;
  items: InventoryCountBatchOption[];
};

export type InventoryCountDifferenceItem = {
  serial_number: number;
  product_id: string;
  product_code?: string | null;
  product_name?: string | null;
  product_description?: string | null;
  batch_no?: string | null;
  manufacture_date?: string | null;
  expiry_date?: string | null;
  counted_quantity: number;
  existing_stock: number;
  difference: number;
};

export type InventoryCountDifferenceResponse = {
  count_number: string;
  count_date: string;
  count_performed_by: string;
  total_items: number;
  items: InventoryCountDifferenceItem[];
};

export type InventoryCountDifferenceReasonCode = {
  code: string;
  label: string;
};

export type InventoryCountDifferenceAcceptPayload = {
  reason_code: string;
};

export type InventoryCountDifferenceActionItem = {
  serial_number: number;
  product_id: string;
  product_code?: string | null;
  product_name?: string | null;
  old_qty: number;
  new_qty: number;
  difference_qty: number;
  reason_code?: string | null;
};

export type InventoryCountDifferenceActionResponse = {
  count_number: string;
  action: string;
  reason_code?: string | null;
  total_rows: number;
  adjusted_rows: number;
  adjusted_total_qty: number;
  message: string;
  items: InventoryCountDifferenceActionItem[];
};

export type InventoryCountNumberSearchResponse = {
  items: string[];
};

export const stockApi = {
  /**
   * Adjust stock for a product
   * @param payload - Adjustment details with quantity (negative to remove)
   */
  adjust: async (payload: StockAdjustmentPayload): Promise<StockLedger> => {
    const response = await apiClient.post<StockLedger>('/api/v1/stock/adjust', payload);
    return response.data;
  },

  /**
   * Get stock ledger transactions for a product
   */
  getLedger: async (productId: string): Promise<StockLedger[]> => {
    const response = await apiClient.get<StockLedger[]>(`/api/v1/stock/ledger/${productId}`);
    return response.data;
  },

  getInventoryCountNumberPreview: async (countDate?: string): Promise<{ count_number: string; count_date: string }> => {
    const response = await apiClient.get<{ count_number: string; count_date: string }>('/api/v1/stock/inventory-counts/next-number', {
      params: countDate ? { count_date: countDate } : {},
    });
    return response.data;
  },

  getInventoryCountBatchOptions: async (productId: string): Promise<InventoryCountBatchOptionsResponse> => {
    const response = await apiClient.get<InventoryCountBatchOptionsResponse>('/api/v1/stock/inventory-counts/batch-options', {
      params: { product_id: productId },
    });
    return response.data;
  },

  createInventoryCount: async (payload: InventoryCountCreatePayload): Promise<InventoryCountResponse> => {
    const response = await apiClient.post<InventoryCountResponse>('/api/v1/stock/inventory-counts', payload);
    return response.data;
  },

  searchInventoryCountNumbers: async (query: string, limit = 10): Promise<InventoryCountNumberSearchResponse> => {
    const response = await apiClient.get<InventoryCountNumberSearchResponse>('/api/v1/stock/inventory-counts/search', {
      params: { q: query, limit },
    });
    return response.data;
  },

  getAllInventoryCountDifferences: async (limit = 300): Promise<InventoryCountDifferenceResponse[]> => {
    const response = await apiClient.get<InventoryCountDifferenceResponse[]>('/api/v1/stock/inventory-counts/differences', {
      params: { limit },
    });
    return response.data;
  },

  getInventoryCountDifference: async (countNumber: string): Promise<InventoryCountDifferenceResponse> => {
    const response = await apiClient.get<InventoryCountDifferenceResponse>(`/api/v1/stock/inventory-counts/${encodeURIComponent(countNumber)}/difference`);
    return response.data;
  },

  getInventoryCountDifferenceReasonCodes: async (): Promise<InventoryCountDifferenceReasonCode[]> => {
    const response = await apiClient.get<InventoryCountDifferenceReasonCode[]>('/api/v1/stock/inventory-counts/differences/reason-codes');
    return response.data;
  },

  acceptInventoryCountDifference: async (
    countNumber: string,
    payload: InventoryCountDifferenceAcceptPayload,
  ): Promise<InventoryCountDifferenceActionResponse> => {
    const response = await apiClient.post<InventoryCountDifferenceActionResponse>(
      `/api/v1/stock/inventory-counts/${encodeURIComponent(countNumber)}/differences/accept`,
      payload,
    );
    return response.data;
  },

  recountInventoryCountDifference: async (countNumber: string): Promise<InventoryCountDifferenceActionResponse> => {
    const response = await apiClient.post<InventoryCountDifferenceActionResponse>(
      `/api/v1/stock/inventory-counts/${encodeURIComponent(countNumber)}/differences/recount`,
      {},
    );
    return response.data;
  },
};
