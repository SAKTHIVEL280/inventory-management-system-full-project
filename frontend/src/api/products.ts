import { apiClient } from './client';
import { Product, ProductCategory, UnitOfMeasure, PaginatedResponse } from '../types';

export const productsApi = {
  list: async (): Promise<PaginatedResponse<Product>> => {
    const response = await apiClient.get<PaginatedResponse<Product>>('/api/v1/products');
    return response.data;
  },

  listCategories: async (): Promise<ProductCategory[]> => {
    const response = await apiClient.get<ProductCategory[]>('/api/v1/products/categories');
    return response.data;
  },

  createCategory: async (payload: Pick<ProductCategory, 'name' | 'description'>): Promise<ProductCategory> => {
    const response = await apiClient.post<ProductCategory>('/api/v1/products/categories', payload);
    return response.data;
  },

  listUom: async (): Promise<UnitOfMeasure[]> => {
    const response = await apiClient.get<UnitOfMeasure[]>('/api/v1/products/uom');
    return response.data;
  },

  create: async (payload: Omit<Product, 'id' | 'current_stock' | 'low_stock'>): Promise<Product> => {
    const response = await apiClient.post<Product>('/api/v1/products', payload);
    return response.data;
  },
};
