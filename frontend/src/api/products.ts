import { apiClient } from './client';
import { Product, ProductCategory, UnitOfMeasure, PaginatedResponse } from '../types';

type CreateProductPayload = {
  product_code?: string | null;
  sku?: string | null;
  name: string;
  description?: string | null;
  category_id: string;
  uom_id: string;
  alt_uom_id?: string | null;
  alt_uom_conversion?: number | null;
  hsn_code: string;
  gst_rate: 0 | 5 | 12 | 18 | 28;
  purchase_price: number;
  selling_price: number;
  mrp: number;
  minimum_stock: number;
  opening_stock: number;
  is_active: boolean;
};

export const productsApi = {
  list: async (): Promise<PaginatedResponse<Product>> => {
    const response = await apiClient.get<PaginatedResponse<Product>>('/api/v1/products');
    return response.data;
  },

  get: async (id: string): Promise<Product> => {
    const response = await apiClient.get<Product>(`/api/v1/products/${id}`);
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

  updateCategory: async (id: string, payload: Partial<ProductCategory>): Promise<ProductCategory> => {
    const response = await apiClient.put<ProductCategory>(`/api/v1/products/categories/${id}`, payload);
    return response.data;
  },

  deleteCategory: async (id: string): Promise<void> => {
    await apiClient.delete(`/api/v1/products/categories/${id}`);
  },

  listUom: async (): Promise<UnitOfMeasure[]> => {
    const response = await apiClient.get<UnitOfMeasure[]>('/api/v1/products/uom');
    return response.data;
  },

  create: async (payload: CreateProductPayload): Promise<Product> => {
    const response = await apiClient.post<Product>('/api/v1/products', payload);
    return response.data;
  },

  update: async (id: string, payload: Partial<CreateProductPayload>): Promise<Product> => {
    const response = await apiClient.put<Product>(`/api/v1/products/${id}`, payload);
    return response.data;
  },

  delete: async (id: string): Promise<void> => {
    await apiClient.delete(`/api/v1/products/${id}`);
  },
};
