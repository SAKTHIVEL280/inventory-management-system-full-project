import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { productsApi } from '../api/products';
import { Product } from '../types';
import { AppLayout } from '../components/AppLayout';
import { PageEmpty, PageError, PageLoading } from '../components/PageState';

const categorySchema = z.object({
  name: z.string().min(1, 'Category name required'),
  description: z.string().optional(),
});

const productSchema = z.object({
  name: z.string().min(1, 'Product name required'),
  hsn_code: z.string().min(6, 'HSN must be 6-8 digits').max(8, 'HSN must be 6-8 digits'),
  gst_rate: z.enum(['0', '5', '12', '18', '28']),
  purchase_price: z.coerce.number().min(0),
  selling_price: z.coerce.number().min(0),
  mrp: z.coerce.number().min(0),
  minimum_stock: z.coerce.number().min(0),
  opening_stock: z.coerce.number().min(0),
  category_id: z.string().min(1, 'Category required'),
  uom_id: z.string().min(1, 'UoM required'),
});

type CategoryForm = z.infer<typeof categorySchema>;
type ProductForm = z.infer<typeof productSchema>;

const ProductsPage = () => {
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState('');
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'product' | 'category'>('product');

  const productsQuery = useQuery({ queryKey: ['products'], queryFn: productsApi.list });
  const categoriesQuery = useQuery({ queryKey: ['product-categories'], queryFn: productsApi.listCategories });
  const uomQuery = useQuery({ queryKey: ['uom'], queryFn: productsApi.listUom });

  const categoryForm = useForm<CategoryForm>({ defaultValues: { name: '', description: '' } });
  const productForm = useForm<ProductForm>({
    defaultValues: {
      name: '', hsn_code: '', gst_rate: '18',
      purchase_price: 0, selling_price: 0, mrp: 0,
      minimum_stock: 0, opening_stock: 0, category_id: '', uom_id: '',
    },
  });

  const categoryMutation = useMutation({
    mutationFn: productsApi.createCategory,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['product-categories'] });
      categoryForm.reset();
    },
  });

  const productMutation = useMutation({
    mutationFn: (payload: Omit<Product, 'id' | 'current_stock' | 'low_stock'>) => productsApi.create(payload),
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
    mutationFn: ({ id, payload }: { id: string; payload: Partial<Product> }) => productsApi.update(id, payload),
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
        setFormError('Failed to update product');
      }
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => productsApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
      setDeleteConfirm(null);
    },
  });

  const resetProductForm = () => {
    setEditingProduct(null);
    setFormError('');
    productForm.reset();
  };

  const startEditProduct = (item: Product) => {
    setEditingProduct(item);
    setActiveTab('product');
    setFormError('');
    productForm.setValue('name', item.name);
    productForm.setValue('hsn_code', item.hsn_code);
    productForm.setValue('gst_rate', String(item.gst_rate) as '0' | '5' | '12' | '18' | '28');
    productForm.setValue('purchase_price', item.purchase_price / 100);
    productForm.setValue('selling_price', item.selling_price / 100);
    productForm.setValue('mrp', item.mrp / 100);
    productForm.setValue('minimum_stock', item.minimum_stock);
    productForm.setValue('opening_stock', item.opening_stock);
    productForm.setValue('category_id', item.category_id);
    productForm.setValue('uom_id', item.uom_id);
  };

  const onCreateCategory = (values: CategoryForm): void => {
    const parsed = categorySchema.safeParse(values);
    if (!parsed.success) {
      setFormError(parsed.error.issues[0]?.message ?? 'Validation failed');
      return;
    }
    categoryMutation.mutate(parsed.data);
  };

  const onCreateProduct = (values: ProductForm): void => {
    const parsed = productSchema.safeParse(values);
    if (!parsed.success) {
      setFormError(parsed.error.issues[0]?.message ?? 'Validation failed');
      return;
    }

    const payload = {
      product_code: undefined,
      sku: null,
      name: parsed.data.name.trim(),
      description: null,
      category_id: parsed.data.category_id,
      uom_id: parsed.data.uom_id,
      alt_uom_id: null,
      alt_uom_conversion: null,
      hsn_code: parsed.data.hsn_code,
      gst_rate: Number(parsed.data.gst_rate) as Product['gst_rate'],
      purchase_price: Math.round(parsed.data.purchase_price * 100),
      selling_price: Math.round(parsed.data.selling_price * 100),
      mrp: Math.round(parsed.data.mrp * 100),
      minimum_stock: Math.round(parsed.data.minimum_stock),
      opening_stock: Math.round(parsed.data.opening_stock),
      is_active: true,
    };

    if (editingProduct) {
      updateMutation.mutate({ id: editingProduct.id, payload });
    } else {
      productMutation.mutate(payload);
    }
  };

  const products = productsQuery.data?.items ?? [];
  const isSaving = productMutation.isPending || updateMutation.isPending;

  return (
    <AppLayout title="Product Master">
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="hms-card xl:col-span-1 overflow-hidden">
          {/* Tab Switcher */}
          <div className="flex border-b border-neutral-200">
            <button
              type="button"
              onClick={() => { setActiveTab('product'); resetProductForm(); }}
              className={`flex-1 px-4 py-3 text-sm font-semibold transition ${activeTab === 'product' ? 'border-b-2 border-primary text-primary bg-primary/5' : 'text-neutral-500 hover:text-neutral-700'}`}
            >
              {editingProduct ? 'Edit Product' : 'Add Product'}
            </button>
            <button
              type="button"
              onClick={() => { setActiveTab('category'); resetProductForm(); }}
              className={`flex-1 px-4 py-3 text-sm font-semibold transition ${activeTab === 'category' ? 'border-b-2 border-primary text-primary bg-primary/5' : 'text-neutral-500 hover:text-neutral-700'}`}
            >
              Add Category
            </button>
          </div>

          <div className="p-5">
            {activeTab === 'category' && (
              <form className="space-y-3" onSubmit={categoryForm.handleSubmit(onCreateCategory)}>
                <div>
                  <label htmlFor="category_name" className="hms-label">Category name</label>
                  <input id="category_name" className="hms-input" placeholder="Category name" {...categoryForm.register('name')} />
                </div>
                <div>
                  <label htmlFor="category_description" className="hms-label">Description</label>
                  <input id="category_description" className="hms-input" placeholder="Description" {...categoryForm.register('description')} />
                </div>
                {categoryMutation.isError && <p className="text-sm text-danger">Failed to create category</p>}
                {categoryMutation.isSuccess && <p className="text-sm text-success">Category created</p>}
                <button type="submit" disabled={categoryMutation.isPending} className="w-full rounded-lg bg-primary px-5 py-2.5 text-sm font-bold text-white shadow-lg shadow-primary/20 transition hover:bg-primary/90 disabled:opacity-60">
                  {categoryMutation.isPending ? 'Saving...' : 'Create Category'}
                </button>
              </form>
            )}

            {activeTab === 'product' && (
              <>
                {editingProduct && (
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-sm font-semibold text-neutral-900">Editing: {editingProduct.name}</h3>
                    <button type="button" onClick={resetProductForm} className="text-sm text-neutral-500 hover:text-neutral-700">Cancel</button>
                  </div>
                )}
                <form className="space-y-3" onSubmit={productForm.handleSubmit(onCreateProduct)}>
                  <div>
                    <label htmlFor="product_name" className="hms-label">Product name</label>
                    <input id="product_name" className="hms-input" placeholder="Product name" {...productForm.register('name')} />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label htmlFor="hsn_code" className="hms-label">HSN code</label>
                      <input id="hsn_code" className="hms-input" placeholder="e.g. 84713010" {...productForm.register('hsn_code')} />
                    </div>
                    <div>
                      <label htmlFor="gst_rate" className="hms-label">GST rate</label>
                      <select id="gst_rate" className="hms-input" {...productForm.register('gst_rate')}>
                        <option value="0">0%</option><option value="5">5%</option><option value="12">12%</option><option value="18">18%</option><option value="28">28%</option>
                      </select>
                    </div>
                  </div>
                  <div>
                    <label htmlFor="category_id" className="hms-label">Category</label>
                    <select id="category_id" className="hms-input" {...productForm.register('category_id')}>
                      <option value="">Select category</option>
                      {(categoriesQuery.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                    </select>
                  </div>
                  <div>
                    <label htmlFor="uom_id" className="hms-label">Unit of measure</label>
                    <select id="uom_id" className="hms-input" {...productForm.register('uom_id')}>
                      <option value="">Select UoM</option>
                      {(uomQuery.data ?? []).map((u) => <option key={u.id} value={u.id}>{u.name} ({u.abbreviation})</option>)}
                    </select>
                  </div>
                  <div className="grid grid-cols-3 gap-3">
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
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label htmlFor="minimum_stock" className="hms-label">Min. stock</label>
                      <input id="minimum_stock" type="number" className="hms-input" placeholder="0" {...productForm.register('minimum_stock')} />
                    </div>
                    <div>
                      <label htmlFor="opening_stock" className="hms-label">Opening stock</label>
                      <input id="opening_stock" type="number" className="hms-input" placeholder="0" {...productForm.register('opening_stock')} />
                    </div>
                  </div>
                  {formError && <p className="text-sm text-danger">{formError}</p>}
                  {productMutation.isSuccess && <p className="text-sm text-success">Product created successfully</p>}
                  {updateMutation.isSuccess && <p className="text-sm text-success">Product updated successfully</p>}
                  <button type="submit" disabled={isSaving} className="w-full rounded-lg bg-primary px-5 py-2.5 text-sm font-bold text-white shadow-lg shadow-primary/20 transition hover:bg-primary/90 disabled:opacity-60">
                    {isSaving ? 'Saving...' : editingProduct ? 'Update Product' : 'Create Product'}
                  </button>
                </form>
              </>
            )}
          </div>
        </div>

        <div className="hms-card xl:col-span-2 overflow-hidden">
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
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">GST</th>
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Price</th>
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Stock</th>
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Status</th>
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {products.map((item) => (
                  <tr key={item.id} className="hover:bg-neutral-50/80">
                    <td className="px-4 py-3 font-mono text-xs">{item.product_code}</td>
                    <td className="px-4 py-3 font-medium">{item.name}</td>
                    <td className="px-4 py-3">{item.gst_rate}%</td>
                    <td className="px-4 py-3">₹{(item.selling_price / 100).toFixed(2)}</td>
                    <td className="px-4 py-3">{item.current_stock ?? 0}</td>
                    <td className="px-4 py-3">
                      {item.low_stock ? (
                        <span className="rounded-full bg-red-100 px-2.5 py-1 text-xs font-bold text-red-700">Low Stock</span>
                      ) : (
                        <span className="rounded-full bg-green-100 px-2.5 py-1 text-xs font-bold text-green-700">OK</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <button type="button" onClick={() => startEditProduct(item)} className="rounded px-2 py-1 text-xs font-semibold text-primary hover:bg-primary/10 transition">Edit</button>
                        <button type="button" onClick={() => setDeleteConfirm(item.id)} className="rounded px-2 py-1 text-xs font-semibold text-danger hover:bg-red-50 transition">Delete</button>
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
          <div className="hms-card w-full max-w-sm space-y-6 p-6">
            <div>
              <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-red-100">
                <span className="material-icons text-red-600" aria-hidden="true">delete</span>
              </div>
              <h2 className="font-display text-lg font-bold text-neutral-900">Delete Product</h2>
              <p className="mt-2 text-sm text-neutral-600">Are you sure? This action cannot be undone.</p>
            </div>
            <div className="flex gap-3">
              <button type="button" onClick={() => setDeleteConfirm(null)} className="flex-1 rounded-lg border border-neutral-200 bg-white px-4 py-2.5 text-sm font-semibold text-neutral-600 transition hover:bg-neutral-50">Cancel</button>
              <button type="button" onClick={() => deleteMutation.mutate(deleteConfirm)} className="flex-1 rounded-lg bg-red-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-red-600/20 transition hover:bg-red-700">Delete</button>
            </div>
          </div>
        </div>
      )}
    </AppLayout>
  );
};

export default ProductsPage;
