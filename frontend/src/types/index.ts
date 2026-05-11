/**
 * Frontend TypeScript Types
 * 
 * Single source of truth for all API response shapes, authentication objects,
 * and business domain models.
 */

// ============================================================================
// Auth Types
// ============================================================================

export interface User {
  id: string;
  full_name: string;
  email: string;
  role: 'admin' | 'inventory manager' | 'general manager';
  company_id?: string | null;
  permission_overrides?: Record<string, unknown> | null;
  effective_access: string[];
  force_password_change: boolean;
}

export interface AuthToken {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
  confirm_password: string;
}

export interface Company {
  id?: string;
  name: string;
  legal_name?: string | null;
  gstin?: string | null;
  gstin_status?: string;
  pan?: string | null;
  import_export_number?: string | null;
  company_director_name?: string | null;
  company_director_contact?: string | null;
  address_line1?: string | null;
  address_line2?: string | null;
  city?: string | null;
  state?: string | null;
  country?: string | null;
  state_code?: string | null;
  pincode?: string | null;
  phone?: string | null;
  email?: string | null;
  website?: string | null;
  logo_url?: string | null;
  ambassador_logo_url?: string | null;
  bank_name?: string | null;
  account_holder_name?: string | null;
  bank_account_no?: string | null;
  bank_ifsc?: string | null;
  bank_branch?: string | null;
  invoice_prefix: string;
  invoice_counter: number;
  po_prefix: string;
  po_counter: number;
  so_prefix: string;
  so_counter: number;
  qtn_prefix: string;
  qtn_counter: number;
  grn_prefix: string;
  grn_counter: number;
  rdn_prefix: string;
  rdn_counter: number;
}

export interface UserManagement {
  id: string;
  full_name: string;
  email: string;
  role: User['role'];
  permission_overrides?: Record<string, string[]> | null;
  effective_access: string[];
  force_password_change: boolean;
  is_active: boolean;
}

export interface UserCreateRequest {
  full_name: string;
  email: string;
  password: string;
  role: User['role'];
  permission_overrides?: { allow: string[]; deny: string[] } | null;
  is_active: boolean;
}

export interface UserUpdateRequest {
  full_name: string;
  email: string;
  password?: string;
  role: User['role'];
  permission_overrides?: { allow: string[]; deny: string[] } | null;
  is_active: boolean;
}

export interface UserPermissionsRequest {
  allow: string[];
  deny: string[];
}

export interface Customer {
  id: string;
  customer_code?: string;
  company_name: string;
  company_director_name?: string | null;
  company_director_contact?: string | null;
  contact_person?: string | null;
  email?: string | null;
  phone: string;
  alternate_phone?: string | null;
  gstin_status?: 'registered' | 'non-registered';
  gstin?: string | null;
  pan?: string | null;
  customer_type: 'regular' | 'dealer' | 'distributor' | 'retail';
  business_type?: 'domestic' | 'international';
  billing_address_line1?: string | null;
  billing_address_line2?: string | null;
  billing_city?: string | null;
  billing_state?: string | null;
  billing_state_code?: string | null;
  billing_country?: string | null;
  billing_pincode?: string | null;
  shipping_address_line1?: string | null;
  shipping_address_line2?: string | null;
  shipping_city?: string | null;
  shipping_state?: string | null;
  shipping_state_code?: string | null;
  shipping_country?: string | null;
  shipping_pincode?: string | null;
  same_as_billing: boolean;
  credit_limit: number;
  payment_terms_days?: number | null;
  opening_balance: number;
  opening_balance_type: 'dr' | 'cr';
  currency_code: string;
  is_active: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface CustomerCustomizationOptions {
  countries: string[];
  currencies: string[];
  states: string[];
}

export interface Supplier {
  id: string;
  supplier_code?: string;
  company_name: string;
  company_director_name?: string | null;
  company_director_contact?: string | null;
  contact_person?: string | null;
  email?: string | null;
  phone: string;
  alternate_phone?: string | null;
  gstin_status?: 'registered' | 'non-registered';
  gstin?: string | null;
  pan?: string | null;
  business_type?: 'domestic' | 'international';
  address_line1?: string | null;
  address_line2?: string | null;
  city?: string | null;
  state?: string | null;
  state_code?: string | null;
  billing_country?: string | null;
  pincode?: string | null;
  bank_name?: string | null;
  bank_account_no?: string | null;
  bank_ifsc?: string | null;
  place_of_supply?: string | null;
  payment_terms_days: number;
  currency_code: string;
  opening_balance: number;
  opening_balance_type: 'dr' | 'cr';
  is_active: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface SupplierCustomizationOptions {
  countries: string[];
  currencies: string[];
  states: string[];
}

export interface ProductCategory {
  id: string;
  name: string;
  description?: string | null;
  is_active?: boolean;
}

export interface UnitOfMeasure {
  id: string;
  name: string;
  abbreviation: string;
  is_active: boolean;
}

export interface Product {
  id: string;
  product_code?: string;
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
  safety_stock: number;
  opening_stock: number;
  status: 'active' | 'inactive' | 'flagged_for_deletion';
  is_active: boolean;
  current_stock?: number;
  low_stock?: boolean;
  below_safety_stock?: boolean;
}

export interface StockLedger {
  id: string;
  product_id: string;
  transaction_type: string;
  reference_type?: string | null;
  reference_number?: string | null;
  quantity: number;
  rate: number;
  transaction_date: string;
  notes?: string | null;
}

// ============================================================================
// API Response Types
// ============================================================================

export interface ApiResponse<T> {
  data?: T;
  message?: string;
  error?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

// ============================================================================
// Customization Options
// ============================================================================

export interface CustomizationOption {
  id: string;
  module: string;
  field_name: string;
  option_value: string;
  display_label?: string | null;
  sort_order: number;
  is_active: boolean;
  is_deleted?: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface CustomizationOptionsListResponse {
  items: CustomizationOption[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface CustomizationOptionPayload {
  module: string;
  field_name: string;
  option_value: string;
  display_label?: string | null;
  sort_order?: number;
  is_active?: boolean;
}

// ============================================================================
// Return Delivery Note (RDN)
// ============================================================================

export interface RDNReturnReasonOption {
  value: string;
  label: string;
}

export interface RDNCustomizationOptions {
  return_reasons: RDNReturnReasonOption[];
}

export interface RDNOverviewItem {
  rdn_id: string;
  rdn_number: string;
  customer_id: string;
  customer_name: string;
  sales_invoice_id: string;
  invoice_number: string;
  receipt_date: string;
  product_id: string;
  product_code?: string | null;
  product_name?: string | null;
  return_quantity: number;
  mrp?: number | null;
  status: string;
}

export interface RDNOverviewResponse {
  items: RDNOverviewItem[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface RDN {
  id: string;
  rdn_number: string;
  customer_id: string;
  sales_invoice_id: string;
  customer_delivery_number?: string | null;
  customer_delivery_date: string;
  receipt_date: string;
  status: string;
  notes?: string | null;
  created_at?: string | null;
}

export interface RDNItem {
  id: string;
  rdn_id: string;
  product_id: string;
  product_code?: string | null;
  product_name?: string | null;
  invoice_item_id: string;
  batch_no: string;
  manufacture_date: string;
  expiry_date: string;
  invoice_quantity: number;
  return_quantity: number;
  mrp?: number | null;
  reason_code: string;
  reason_label: string;
}

export interface RDNDetailResponse {
  rdn: RDN;
  items: RDNItem[];
}

export interface RDNLineItemPayload {
  product_id: string;
  invoice_item_id: string;
  batch_no: string;
  manufacture_date: string;
  expiry_date: string;
  return_quantity: number;
  reason_code: string;
}

export interface RDNCreatePayload {
  customer_id: string;
  sales_invoice_id: string;
  customer_delivery_number?: string | null;
  customer_delivery_date: string;
  receipt_date: string;
  notes?: string | null;
  items: RDNLineItemPayload[];
}

export interface RDNUpdatePayload extends RDNCreatePayload {}

// ============================================================================
// Constants
// ============================================================================

export const ROLES = {
  ADMIN: 'admin',
  INVENTORY_MANAGER: 'inventory manager',
  GENERAL_MANAGER: 'general manager',
} as const;

export const PERMISSION_SCOPES = {
  // Company
  COMPANY_READ: 'company_read',
  COMPANY_WRITE: 'company_write',
  
  // Users
  USERS_READ: 'users_read',
  USERS_WRITE: 'users_write',
  
  // Masters
  CUSTOMERS_READ: 'customers_read',
  CUSTOMERS_WRITE: 'customers_write',
  SUPPLIERS_READ: 'suppliers_read',
  SUPPLIERS_WRITE: 'suppliers_write',
  PRODUCTS_READ: 'products_read',
  PRODUCTS_WRITE: 'products_write',
  CATEGORIES_READ: 'categories_read',
  CATEGORIES_WRITE: 'categories_write',
  UOM_READ: 'uom_read',
  UOM_WRITE: 'uom_write',
  
  // Purchase
  PURCHASE_ORDERS_READ: 'purchase_orders_read',
  PURCHASE_ORDERS_WRITE: 'purchase_orders_write',
  GRN_READ: 'grn_read',
  GRN_WRITE: 'grn_write',
  PURCHASE_RETURNS_READ: 'purchase_returns_read',
  PURCHASE_RETURNS_WRITE: 'purchase_returns_write',
  
  // Stock
  STOCK_LEDGER_READ: 'stock_ledger_read',
  STOCK_LEDGER_WRITE: 'stock_ledger_write',
  STOCK_ADJUSTMENT_READ: 'stock_adjustment_read',
  STOCK_ADJUSTMENT_WRITE: 'stock_adjustment_write',
  
  // Sales
  QUOTATIONS_READ: 'quotations_read',
  QUOTATIONS_WRITE: 'quotations_write',
  SALES_ORDERS_READ: 'sales_orders_read',
  SALES_ORDERS_WRITE: 'sales_orders_write',
  SALES_INVOICES_READ: 'sales_invoices_read',
  SALES_INVOICES_WRITE: 'sales_invoices_write',
  SALES_RETURNS_READ: 'sales_returns_read',
  SALES_RETURNS_WRITE: 'sales_returns_write',
  RDN_READ: 'rdn_read',
  RDN_WRITE: 'rdn_write',
  
  // Payments
  RECEIPTS_READ: 'receipts_read',
  RECEIPTS_WRITE: 'receipts_write',
  PAYMENTS_READ: 'payments_read',
  PAYMENTS_WRITE: 'payments_write',
  
  // Reports & Dashboard
  REPORTS_READ: 'reports_read',
  ACTION_LOGS_READ: 'action_logs_read',
  DASHBOARD_READ: 'dashboard_read',
} as const;

export type PermissionScope = typeof PERMISSION_SCOPES[keyof typeof PERMISSION_SCOPES];
