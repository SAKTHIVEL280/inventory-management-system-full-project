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

  createInventoryCount: async (payload: InventoryCountCreatePayload): Promise<InventoryCountResponse> => {
    const response = await apiClient.post<InventoryCountResponse>('/api/v1/stock/inventory-counts', payload);
    return response.data;
  },

  getInventoryCountDifference: async (countNumber: string): Promise<InventoryCountDifferenceResponse> => {
    const response = await apiClient.get<InventoryCountDifferenceResponse>(`/api/v1/stock/inventory-counts/${encodeURIComponent(countNumber)}/difference`);
    return response.data;
  },
};
