import { apiClient } from './client';
import { StockLedger } from '../types';

type StockAdjustmentPayload = {
  product_id: string;
  quantity: number;  // Positive for add, negative for remove
  notes?: string | null;
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
};
