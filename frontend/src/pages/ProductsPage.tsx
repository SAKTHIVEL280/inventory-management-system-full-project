import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { productsApi } from '../api/products';
import { stockApi } from '../api/stock';
import { Product } from '../types';
import { AppLayout } from '../components/AppLayout';
import { PageEmpty, PageError, PageLoading } from '../components/PageState';

const productSchema = z.object({
  name: z.string().min(1, 'Product name required'),
  description: z.string().optional(),
  sku: z.string().optional(),
  hsn_code: z.string().min(6, 'HSN must be 6-8 digits').max(8, 'HSN must be 6-8 digits'),
  gst_rate: z.enum(['0', '5', '12', '18', '28']),
  purchase_price: z.coerce.number().min(0),
  selling_price: z.coerce.number().min(0),
  mrp: z.coerce.number().min(0),
  minimum_stock: z.coerce.number().min(0),
  safety_stock: z.coerce.number().min(0),
  opening_stock: z.coerce.number().min(0),
  category_id: z.string().min(1, 'Category required'),
  uom_id: z.string().min(1, 'UoM required'),
  is_active: z.boolean(),
  status: z.enum(['active', 'inactive', 'flagged_for_deletion']).default('active'),
});

type ProductForm = z.infer<typeof productSchema>;

const defaultProductValues: ProductForm = {
  name: '', description: '', sku: '', hsn_code: '', gst_rate: '18',
  purchase_price: 0, selling_price: 0, mrp: 0,
  minimum_stock: 0, safety_stock: 0, opening_stock: 0, category_id: '', uom_id: '',
  is_active: true, status: 'active',
};

const ProductsPage = () => {
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState('');
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<Product | null>(null);
  const [adjustStock, setAdjustStock] = useState<{ productId: string; productName: string; currentStock: number } | null>(null);

  const productsQuery = useQuery({ queryKey: ['products'], queryFn: productsApi.list });
  const categoriesQuery = useQuery({ queryKey: ['product-categories'], queryFn: productsApi.listCategories });
  const uomQuery = useQuery({ queryKey: ['uom'], queryFn: productsApi.listUom });

  const productForm = useForm<ProductForm>({ defaultValues: defaultProductValues });

  const productMutation = useMutation({
    mutationFn: (payload: Parameters<typeof productsApi.create>[0]) => productsApi.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
      resetProductForm();
    },
    onError: (error: unknown) => {
      const axiosErr = error as any;
      const detail = axiosErr.response?.data?.detail;
      if (typeof detail === 'string') {
        setFormError(detail);
      } else if (Array.isArray(detail)) {
        setFormError(detail.map((d: any) => d.msg).join(', '));
      } else {
        setFormError('Failed to create product');
      }
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Parameters<typeof productsApi.update>[1] }) => productsApi.update(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
      resetProductForm();
      setFormError('');
    },
    onError: (error: unknown) => {
      const axiosErr = error as any;
      const detail = axiosErr.response?.data?.detail;
      if (typeof detail === 'string') {
        setFormError(detail);
      } else if (Array.isArray(detail)) {
        setFormError(detail.map((d: any) => d.msg).join(', '));
      } else {
        setFormError('Failed to update product');
      }
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => productsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
      setDeleteConfirm(null);
      setFormError('');
    },
    onError: (error: unknown) => {
      const axiosErr = error as any;
      const detail = axiosErr.response?.data?.detail;
      if (typeof detail === 'string') {
        setFormError(detail);
      } else if (detail?.message) {
        // Handle backend error objects (e.g., stock check errors)
        setFormError(detail.message);
      } else if (Array.isArray(detail)) {
        setFormError(detail.map((d: any) => d.msg).join(', '));
      } else {
        setFormError('Failed to delete product');
      }
    },
  });

  const adjustStockMutation = useMutation({
    mutationFn: (payload: { product_id: string; quantity: number; notes?: string }) => stockApi.adjust(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
      setAdjustStock(null);
      setFormError('');
    },
    onError: (error: unknown) => {
      const axiosErr = error as any;
      const detail = axiosErr.response?.data?.detail;
      if (typeof detail === 'string') {
        setFormError(detail);
      } else if (Array.isArray(detail)) {
        setFormError(detail.map((d: any) => d.msg).join(', '));
      } else {
        setFormError('Failed to adjust stock');
      }
    },
  });

  const resetProductForm = () => {
    setEditingProduct(null);
    setFormError('');
    productForm.reset(defaultProductValues);
    setIsFormOpen(false);
  };

  const startEditProduct = (item: Product) => {
    setEditingProduct(item);
    setIsFormOpen(true);
    setFormError('');
    // Set ALL form fields from the product data
    productForm.reset({
      name: item.name,
      description: item.description ?? '',
      sku: item.sku ?? '',
      hsn_code: item.hsn_code,
      gst_rate: String(item.gst_rate) as '0' | '5' | '12' | '18' | '28',
      purchase_price: item.purchase_price / 100,
      selling_price: item.selling_price / 100,
      mrp: item.mrp / 100,
      minimum_stock: item.minimum_stock,
      safety_stock: item.safety_stock ?? 0,
      opening_stock: item.opening_stock,
      category_id: item.category_id,
      uom_id: item.uom_id,
      is_active: item.status === 'active',
      status: item.status,
    });
  };

  const handleAdjustStockForDelete = (productId: string, productName: string, currentStock: number) => {
    setAdjustStock({ productId, productName, currentStock });
    setDeleteConfirm(null);
  };

  const handleClearStockForDelete = () => {
    if (!adjustStock) return;
    adjustStockMutation.mutate({
      product_id: adjustStock.productId,
      quantity: -adjustStock.currentStock,
      notes: `Stock cleared to enable product deletion`,
    });
  };

  const onCreateProduct = (values: ProductForm): void => {
    const parsed = productSchema.safeParse(values);
    if (!parsed.success) {
      setFormError(parsed.error.issues[0]?.message ?? 'Validation failed');
      return;
    }

    // Build the FULL payload — backend requires all fields, not partial
    const payload = {
      name: parsed.data.name.trim(),
      description: parsed.data.description?.trim() || null,
      sku: parsed.data.sku?.trim() || null,
      category_id: parsed.data.category_id,
      uom_id: parsed.data.uom_id,
      alt_uom_id: null as string | null,
      alt_uom_conversion: null as number | null,
      hsn_code: parsed.data.hsn_code,
      gst_rate: Number(parsed.data.gst_rate) as Product['gst_rate'],
      purchase_price: Math.round(parsed.data.purchase_price * 100),
      selling_price: Math.round(parsed.data.selling_price * 100),
      mrp: Math.round(parsed.data.mrp * 100),
      minimum_stock: Math.round(parsed.data.minimum_stock),
      safety_stock: Math.round(parsed.data.safety_stock),
      opening_stock: editingProduct
        ? editingProduct.opening_stock  // Preserve original on edit
        : Math.round(parsed.data.opening_stock),
      status: parsed.data.status,
      is_active: parsed.data.status === 'active',
    };

    if (editingProduct) {
      // Send full payload (not Partial) to satisfy backend ProductUpdateRequest
      updateMutation.mutate({ id: editingProduct.id, payload });
    } else {
      productMutation.mutate(payload);
    }
  };

  const products = productsQuery.data?.items ?? [];
  const categories = categoriesQuery.data ?? [];
  const uoms = uomQuery.data ?? [];
  const isSaving = productMutation.isPending || updateMutation.isPending;

  const categoryNameById = (id: string) => categories.find((c) => c.id === id)?.name ?? '—';

  return (
    <AppLayout title="Product Master">
      <div className="space-y-6">
        <div className="hms-card overflow-hidden">
          <div className="border-b border-neutral-200 px-5 py-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="font-display text-lg font-bold text-neutral-900">
                  {editingProduct ? 'Modify/Change Product' : 'Add Product'}
                </h2>
                <p className="text-xs text-neutral-500">Use this panel to create or edit product master records.</p>
              </div>
              <div className="flex items-center gap-2">
                {!isFormOpen && (
                  <button
                    type="button"
                    onClick={() => {
                      setEditingProduct(null);
                      setFormError('');
                      productForm.reset(defaultProductValues);
                      setIsFormOpen(true);
                    }}
                    className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white transition hover:bg-primary/90"
                  >
                    + New Product
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setIsFormOpen((prev) => !prev)}
                  className="inline-flex items-center gap-1 rounded-lg border border-neutral-200 px-3 py-2 text-sm font-semibold text-neutral-700 transition hover:bg-neutral-50"
                >
                  <span className="material-icons text-base" aria-hidden="true">{isFormOpen ? 'expand_less' : 'expand_more'}</span>
                  {isFormOpen ? 'Hide Form' : 'Show Form'}
                </button>
              </div>
            </div>
          </div>

          {isFormOpen && (
            <div className="p-5">
              {editingProduct && (
                <div className="mb-4 flex items-center justify-between border-b border-neutral-200 pb-4">
                  <h3 className="text-sm font-semibold text-neutral-900">Modifying/Changing: {editingProduct.name}</h3>
                  <button type="button" onClick={resetProductForm} className="text-sm text-neutral-500 hover:text-neutral-700">Cancel</button>
                </div>
              )}
              <form className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4" onSubmit={productForm.handleSubmit(onCreateProduct)}>
                <div className="xl:col-span-2">
                  <label htmlFor="product_name" className="hms-label">Product name *</label>
                  <input id="product_name" className="hms-input" placeholder="Product name" {...productForm.register('name')} />
                </div>
                <div>
                  <label htmlFor="product_sku" className="hms-label">SKU</label>
                  <input id="product_sku" className="hms-input" placeholder="SKU code (optional)" {...productForm.register('sku')} />
                </div>
                <div>
                  <label htmlFor="hsn_code" className="hms-label">HSN code *</label>
                  <input id="hsn_code" className="hms-input" placeholder="e.g. 84713010" {...productForm.register('hsn_code')} />
                </div>
                <div className="xl:col-span-2">
                  <label htmlFor="product_description" className="hms-label">Description</label>
                  <input id="product_description" className="hms-input" placeholder="Short description (optional)" {...productForm.register('description')} />
                </div>
                <div>
                  <label htmlFor="category_id" className="hms-label">Category *</label>
                  <select id="category_id" className="hms-input" {...productForm.register('category_id')}>
                    <option value="">Select category</option>
                    {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </div>
                <div>
                  <label htmlFor="uom_id" className="hms-label">Unit of measure *</label>
                  <select id="uom_id" className="hms-input" {...productForm.register('uom_id')}>
                    <option value="">Select UoM</option>
                    {uoms.map((u) => <option key={u.id} value={u.id}>{u.name} ({u.abbreviation})</option>)}
                  </select>
                </div>
                <div>
                  <label htmlFor="gst_rate" className="hms-label">GST rate *</label>
                  <select id="gst_rate" className="hms-input" {...productForm.register('gst_rate')}>
                    <option value="0">0%</option><option value="5">5%</option><option value="12">12%</option><option value="18">18%</option><option value="28">28%</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="purchase_price" className="hms-label">Purchase ₹</label>
                  <input id="purchase_price" type="number" step="0.01" className="hms-input" placeholder="0.00" {...productForm.register('purchase_price')} />
                </div>
                <div>
                  <label htmlFor="selling_price" className="hms-label">Selling ₹</label>
                  <input id="selling_price" type="number" step="0.01" className="hms-input" placeholder="0.00" {...productForm.register('selling_price')} />
                </div>
                <div>
                  <label htmlFor="mrp" className="hms-label">MRP ₹</label>
                  <input id="mrp" type="number" step="0.01" className="hms-input" placeholder="0.00" {...productForm.register('mrp')} />
                </div>
                <div>
                  <label htmlFor="minimum_stock" className="hms-label">Min. stock</label>
                  <input id="minimum_stock" type="number" className="hms-input" placeholder="0" {...productForm.register('minimum_stock')} />
                </div>
                <div>
                  <label htmlFor="safety_stock" className="hms-label">Safety stock</label>
                  <input id="safety_stock" type="number" className="hms-input" placeholder="0" {...productForm.register('safety_stock')} />
                </div>
                <div>
                  <label htmlFor="opening_stock" className="hms-label">
                    Opening stock {editingProduct && <span className="text-xs text-neutral-400">(read-only)</span>}
                  </label>
                  <input
                    id="opening_stock"
                    type="number"
                    className="hms-input"
                    placeholder="0"
                    disabled={!!editingProduct}
                    {...productForm.register('opening_stock')}
                  />
                </div>
                <div>
                  <label htmlFor="status" className="hms-label">Status</label>
                  <select id="status" className="hms-input" {...productForm.register('status')}>
                    <option value="active">Active</option>
                    <option value="inactive">Inactive</option>
                    <option value="flagged_for_deletion">Flagged for deletion</option>
                  </select>
                </div>

                <div className="md:col-span-2 xl:col-span-4">
                  {formError && <p className="text-sm text-danger">{formError}</p>}
                  {productMutation.isSuccess && !editingProduct && <p className="text-sm text-success">Product created successfully</p>}
                  {updateMutation.isSuccess && <p className="text-sm text-success">Product updated successfully</p>}
                </div>
                <div className="md:col-span-2 xl:col-span-4">
                  <button type="submit" disabled={isSaving} className="rounded-lg bg-primary px-5 py-2.5 text-sm font-bold text-white shadow-lg shadow-primary/20 transition hover:bg-primary/90 disabled:opacity-60">
                    {isSaving ? 'Saving...' : editingProduct ? 'Update Product' : 'Create Product'}
                  </button>
                </div>
              </form>
            </div>
          )}
        </div>

        <div className="hms-card overflow-hidden">
          <div className="border-b border-neutral-200 px-5 py-4">
            <h2 className="font-display text-lg font-bold text-neutral-900">Products</h2>
          </div>
          <div className="p-5">
          {(productsQuery.isLoading || categoriesQuery.isLoading || uomQuery.isLoading) && <PageLoading message="Loading products..." />}
          {(productsQuery.isError || categoriesQuery.isError || uomQuery.isError) && <PageError message="Failed to load product data" />}
          {!productsQuery.isLoading && !productsQuery.isError && products.length === 0 && <PageEmpty message="No products found. Create a category first, then add products." />}
          {!productsQuery.isLoading && !productsQuery.isError && products.length > 0 && (
            <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <caption className="sr-only">Products list with tax and stock status</caption>
              <thead className="bg-neutral-50">
                <tr className="text-left border-y border-neutral-200">
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Code</th>
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Name</th>
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Category</th>
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">GST</th>
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Purchase ₹</th>
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Selling ₹</th>
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">MRP ₹</th>
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Stock</th>
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Status</th>
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {products.map((item) => (
                  <tr key={item.id} className={`hover:bg-neutral-50/80 ${!item.is_active ? 'opacity-50' : ''}`}>
                    <td className="px-4 py-3 font-mono text-xs">{item.product_code}</td>
                    <td className="px-4 py-3">
                      <div className="font-medium">{item.name}</div>
                      {item.sku && <div className="text-xs text-neutral-400">SKU: {item.sku}</div>}
                    </td>
                    <td className="px-4 py-3 text-xs">{categoryNameById(item.category_id)}</td>
                    <td className="px-4 py-3">{item.gst_rate}%</td>
                    <td className="px-4 py-3">₹{(item.purchase_price / 100).toFixed(2)}</td>
                    <td className="px-4 py-3">₹{(item.selling_price / 100).toFixed(2)}</td>
                    <td className="px-4 py-3">₹{(item.mrp / 100).toFixed(2)}</td>
                    <td className="px-4 py-3">{item.current_stock ?? 0}</td>
                    <td className="px-4 py-3">
                      {item.status === 'flagged_for_deletion' ? (
                        <span className="rounded-full bg-red-100 px-2.5 py-1 text-xs font-bold text-red-700">Flagged</span>
                      ) : item.status === 'inactive' ? (
                        <span className="rounded-full bg-neutral-100 px-2.5 py-1 text-xs font-bold text-neutral-500">Inactive</span>
                      ) : item.low_stock ? (
                        <span className="rounded-full bg-red-100 px-2.5 py-1 text-xs font-bold text-red-700">Low Stock</span>
                      ) : item.below_safety_stock ? (
                        <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-bold text-amber-700">Below Safety</span>
                      ) : (
                        <span className="rounded-full bg-green-100 px-2.5 py-1 text-xs font-bold text-green-700">OK</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <button type="button" onClick={() => startEditProduct(item)} className="rounded px-2 py-1 text-xs font-semibold text-primary hover:bg-primary/10 transition">Modify/Change</button>
                        <button type="button" onClick={() => setDeleteConfirm(item)} className="rounded px-2 py-1 text-xs font-semibold text-danger hover:bg-red-50 transition">Delete</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          )}
          </div>
        </div>
      </div>

      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
          <div className="hms-card w-full max-w-md space-y-6 p-6">
            <div>
              <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-red-100">
                <span className="material-icons text-red-600 text-2xl" aria-hidden="true">delete</span>
              </div>
              <h2 className="font-display text-lg font-bold text-neutral-900">Delete Product</h2>
              <p className="mt-2 text-sm text-neutral-600">
                Are you sure you want to delete <strong>{deleteConfirm.name}</strong>? This action cannot be undone.
              </p>

              {/* Stock warning */}
              {(deleteConfirm.current_stock ?? 0) > 0 && (
                <div className="mt-4 rounded-lg bg-amber-50 border border-amber-200 p-4">
                  <div className="flex items-start gap-3">
                    <span className="material-icons text-amber-600 text-lg flex-shrink-0" aria-hidden="true">warning</span>
                    <div className="flex-1">
                      <p className="text-sm font-semibold text-amber-800">Product has existing stock</p>
                      <p className="text-xs text-amber-700 mt-1">
                        Current stock: <strong>{deleteConfirm.current_stock}</strong> units.
                        You must clear the stock to zero before deleting this product. Click the button below to automatically adjust stock.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Error message - shown prominently */}
              {deleteMutation.isError && formError && (
                <div className="mt-4 rounded-lg bg-red-50 border border-red-200 p-4">
                  <div className="flex items-start gap-3">
                    <span className="material-icons text-red-600 text-lg flex-shrink-0" aria-hidden="true">error</span>
                    <p className="text-sm text-red-800 font-medium">{formError}</p>
                  </div>
                </div>
              )}
              
              {deleteMutation.isPending && (
                <div className="mt-4 flex items-center gap-3 text-sm text-neutral-600">
                  <span className="material-icons animate-spin">progress_activity</span>
                  Deleting product...
                </div>
              )}
            </div>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => {
                  setDeleteConfirm(null);
                  setFormError('');
                }}
                className="flex-1 rounded-lg border border-neutral-200 bg-white px-4 py-2.5 text-sm font-semibold text-neutral-600 transition hover:bg-neutral-50 disabled:opacity-50"
                disabled={deleteMutation.isPending}
              >
                Cancel
              </button>

              {(deleteConfirm.current_stock ?? 0) > 0 ? (
                <button
                  type="button"
                  onClick={() => handleAdjustStockForDelete(deleteConfirm.id, deleteConfirm.name, deleteConfirm.current_stock ?? 0)}
                  disabled={deleteMutation.isPending}
                  className="flex-1 rounded-lg bg-amber-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-amber-600/20 transition hover:bg-amber-700 disabled:opacity-50"
                >
                  <span className="material-icons text-sm align-middle mr-1">inventory_2</span>
                  Clear Stock ({deleteConfirm.current_stock} units)
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => deleteMutation.mutate(deleteConfirm.id)}
                  disabled={deleteMutation.isPending}
                  className="flex-1 rounded-lg bg-red-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-red-600/20 transition hover:bg-red-700 disabled:opacity-50"
                >
                  <span className="material-icons text-sm align-middle mr-1">delete</span>
                  {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Stock Adjustment Dialog */}
      {adjustStock && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
          <div className="hms-card w-full max-w-md space-y-6 p-6">
            <div>
              <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-amber-100">
                <span className="material-icons text-amber-600" aria-hidden="true">inventory_2</span>
              </div>
              <h2 className="font-display text-lg font-bold text-neutral-900">Clear Stock for Deletion</h2>
              <p className="mt-2 text-sm text-neutral-600">
                Product: <strong>{adjustStock.productName}</strong>
              </p>
              <div className="mt-4 rounded-lg bg-amber-50 border border-amber-200 p-4">
                <p className="text-sm text-amber-800">
                  Current stock: <strong className="text-lg">{adjustStock.currentStock}</strong> units
                </p>
                <p className="text-xs text-amber-700 mt-2">
                  Clicking "Clear Stock" will create a stock adjustment entry to remove all {adjustStock.currentStock} units. 
                  After this, you can delete the product.
                </p>
              </div>
              {adjustStockMutation.isError && formError && (
                <p className="mt-3 text-sm text-danger font-medium">{formError}</p>
              )}
              {adjustStockMutation.isPending && (
                <p className="mt-3 text-sm text-neutral-500">Adjusting stock...</p>
              )}
              {adjustStockMutation.isSuccess && (
                <p className="mt-3 text-sm text-success font-medium">Stock cleared successfully! You can now delete the product.</p>
              )}
            </div>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => {
                  setAdjustStock(null);
                  setFormError('');
                }}
                className="flex-1 rounded-lg border border-neutral-200 bg-white px-4 py-2.5 text-sm font-semibold text-neutral-600 transition hover:bg-neutral-50 disabled:opacity-50"
                disabled={adjustStockMutation.isPending}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleClearStockForDelete}
                disabled={adjustStockMutation.isPending}
                className="flex-1 rounded-lg bg-amber-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-amber-600/20 transition hover:bg-amber-700 disabled:opacity-50"
              >
                {adjustStockMutation.isPending ? 'Clearing...' : `Clear ${adjustStock.currentStock} Units`}
              </button>
            </div>
            {adjustStockMutation.isSuccess && (
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setAdjustStock(null);
                    setDeleteConfirm({ id: adjustStock.productId, name: adjustStock.productName, current_stock: 0 } as Product);
                  }}
                  className="flex-1 rounded-lg bg-red-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-red-600/20 transition hover:bg-red-700"
                >
                  Now Delete Product
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </AppLayout>
  );
};

export default ProductsPage;
