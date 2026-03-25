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

  const productsQuery = useQuery({ queryKey: ['products'], queryFn: productsApi.list });
  const categoriesQuery = useQuery({ queryKey: ['product-categories'], queryFn: productsApi.listCategories });
  const uomQuery = useQuery({ queryKey: ['uom'], queryFn: productsApi.listUom });

  const categoryForm = useForm<CategoryForm>({ defaultValues: { name: '', description: '' } });
  const productForm = useForm<ProductForm>({
    defaultValues: {
      name: '',
      hsn_code: '',
      gst_rate: '18',
      purchase_price: 0,
      selling_price: 0,
      mrp: 0,
      minimum_stock: 0,
      opening_stock: 0,
      category_id: '',
      uom_id: '',
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
      productForm.reset();
      setFormError('');
    },
  });

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

    productMutation.mutate({
      product_code: '',
      sku: '',
      description: '',
      alt_uom_id: null,
      alt_uom_conversion: null,
      is_active: true,
      ...parsed.data,
      gst_rate: Number(parsed.data.gst_rate) as Product['gst_rate'],
      purchase_price: Math.round(parsed.data.purchase_price),
      selling_price: Math.round(parsed.data.selling_price),
      mrp: Math.round(parsed.data.mrp),
      minimum_stock: Math.round(parsed.data.minimum_stock),
      opening_stock: Math.round(parsed.data.opening_stock),
    });
  };

  const products = productsQuery.data?.items ?? [];

  return (
    <AppLayout title="Product Master">
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className="bg-white border border-neutral-200 rounded p-4 space-y-6">
          <div>
            <h2 className="text-base font-semibold mb-3">Add Category</h2>
            <form className="space-y-3" onSubmit={categoryForm.handleSubmit(onCreateCategory)}>
              <label htmlFor="category_name" className="text-sm text-neutral-700">Category name</label>
              <input id="category_name" className="w-full border border-neutral-300 rounded px-3 py-2" placeholder="Category name" {...categoryForm.register('name')} />
              <label htmlFor="category_description" className="text-sm text-neutral-700">Description</label>
              <input id="category_description" className="w-full border border-neutral-300 rounded px-3 py-2" placeholder="Description" {...categoryForm.register('description')} />
              {categoryMutation.isError && <p className="text-sm text-danger" role="alert" aria-live="assertive">Failed to create category</p>}
              {categoryMutation.isSuccess && <p className="text-sm text-success" role="status" aria-live="polite">Category created successfully</p>}
              <button type="submit" disabled={categoryMutation.isPending} className="w-full bg-primary text-white rounded px-3 py-2">
                {categoryMutation.isPending ? 'Saving...' : 'Create Category'}
              </button>
            </form>
          </div>

          <div>
            <h2 className="text-base font-semibold mb-3">Add Product</h2>
            <form className="space-y-3" onSubmit={productForm.handleSubmit(onCreateProduct)}>
              <label htmlFor="product_name" className="text-sm text-neutral-700">Product name</label>
              <input id="product_name" className="w-full border border-neutral-300 rounded px-3 py-2" placeholder="Product name" {...productForm.register('name')} />
              <label htmlFor="hsn_code" className="text-sm text-neutral-700">HSN code</label>
              <input id="hsn_code" className="w-full border border-neutral-300 rounded px-3 py-2" placeholder="HSN code" {...productForm.register('hsn_code')} />
              <label htmlFor="gst_rate" className="text-sm text-neutral-700">GST rate</label>
              <select id="gst_rate" className="w-full border border-neutral-300 rounded px-3 py-2" {...productForm.register('gst_rate')}>
                <option value="0">0%</option><option value="5">5%</option><option value="12">12%</option><option value="18">18%</option><option value="28">28%</option>
              </select>
              <label htmlFor="category_id" className="text-sm text-neutral-700">Category</label>
              <select id="category_id" className="w-full border border-neutral-300 rounded px-3 py-2" {...productForm.register('category_id')}>
                <option value="">Select category</option>
                {(categoriesQuery.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              <label htmlFor="uom_id" className="text-sm text-neutral-700">Unit of measure</label>
              <select id="uom_id" className="w-full border border-neutral-300 rounded px-3 py-2" {...productForm.register('uom_id')}>
                <option value="">Select UoM</option>
                {(uomQuery.data ?? []).map((u) => <option key={u.id} value={u.id}>{u.abbreviation}</option>)}
              </select>
              <label htmlFor="purchase_price" className="text-sm text-neutral-700">Purchase price (paise)</label>
              <input id="purchase_price" type="number" className="w-full border border-neutral-300 rounded px-3 py-2" placeholder="Purchase price (paise)" {...productForm.register('purchase_price')} />
              <label htmlFor="selling_price" className="text-sm text-neutral-700">Selling price (paise)</label>
              <input id="selling_price" type="number" className="w-full border border-neutral-300 rounded px-3 py-2" placeholder="Selling price (paise)" {...productForm.register('selling_price')} />
              <label htmlFor="mrp" className="text-sm text-neutral-700">MRP (paise)</label>
              <input id="mrp" type="number" className="w-full border border-neutral-300 rounded px-3 py-2" placeholder="MRP (paise)" {...productForm.register('mrp')} />
              <label htmlFor="minimum_stock" className="text-sm text-neutral-700">Minimum stock</label>
              <input id="minimum_stock" type="number" className="w-full border border-neutral-300 rounded px-3 py-2" placeholder="Minimum stock" {...productForm.register('minimum_stock')} />
              <label htmlFor="opening_stock" className="text-sm text-neutral-700">Opening stock</label>
              <input id="opening_stock" type="number" className="w-full border border-neutral-300 rounded px-3 py-2" placeholder="Opening stock" {...productForm.register('opening_stock')} />
              {formError && <p className="text-sm text-danger" role="alert" aria-live="assertive">{formError}</p>}
              {productMutation.isError && <p className="text-sm text-danger" role="alert" aria-live="assertive">Failed to create product</p>}
              {productMutation.isSuccess && <p className="text-sm text-success" role="status" aria-live="polite">Product created successfully</p>}
              <button type="submit" disabled={productMutation.isPending} className="w-full bg-primary text-white rounded px-3 py-2">
                {productMutation.isPending ? 'Saving...' : 'Create Product'}
              </button>
            </form>
          </div>
        </div>

        <div className="xl:col-span-2 bg-white border border-neutral-200 rounded p-4">
          <h2 className="text-base font-semibold mb-3">Products</h2>
          {(productsQuery.isLoading || categoriesQuery.isLoading || uomQuery.isLoading) && <PageLoading message="Loading products..." />}
          {(productsQuery.isError || categoriesQuery.isError || uomQuery.isError) && <PageError message="Failed to load product data" />}
          {!productsQuery.isLoading && !productsQuery.isError && products.length === 0 && <PageEmpty message="No products found" />}
          {!productsQuery.isLoading && !productsQuery.isError && products.length > 0 && (
            <table className="w-full text-sm">
              <caption className="sr-only">Products list with tax and stock status</caption>
              <thead>
                <tr className="text-left border-b border-neutral-200">
                  <th scope="col" className="py-2">Code</th>
                  <th scope="col" className="py-2">Name</th>
                  <th scope="col" className="py-2">GST</th>
                  <th scope="col" className="py-2">Stock</th>
                  <th scope="col" className="py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {products.map((item) => (
                  <tr key={item.id} className="border-b border-neutral-100">
                    <td className="py-2">{item.product_code}</td>
                    <td className="py-2">{item.name}</td>
                    <td className="py-2">{item.gst_rate}%</td>
                    <td className="py-2">{item.current_stock ?? 0}</td>
                    <td className="py-2">{item.low_stock ? <span className="text-danger">Low Stock</span> : 'OK'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </AppLayout>
  );
};

export default ProductsPage;
