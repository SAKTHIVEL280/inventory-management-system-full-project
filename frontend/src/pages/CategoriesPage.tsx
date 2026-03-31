import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { productsApi } from '../api/products';
import { ProductCategory } from '../types';
import { AppLayout } from '../components/AppLayout';
import { PageEmpty, PageError, PageLoading } from '../components/PageState';

const categorySchema = z.object({
  name: z.string().min(1, 'Category name required'),
  description: z.string().optional(),
});

type CategoryForm = z.infer<typeof categorySchema>;

type ApiValidationIssue = {
  msg?: string;
};

type ApiErrorResponse = {
  detail?: string | ApiValidationIssue[];
};

const getErrorMessage = (error: unknown, fallback: string): string => {
  const axiosLikeError = error as { response?: { data?: ApiErrorResponse } };
  const detail = axiosLikeError.response?.data?.detail;

  if (typeof detail === 'string') {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg ?? 'Unknown error').join(', ');
  }

  return fallback;
};

const CategoriesPage = () => {
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState('');
  const [editingCategory, setEditingCategory] = useState<ProductCategory | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<ProductCategory | null>(null);

  const categoriesQuery = useQuery({
    queryKey: ['product-categories'],
    queryFn: productsApi.listCategories,
  });

  const categoryForm = useForm<CategoryForm>({
    defaultValues: { name: '', description: '' },
  });

  const categoryMutation = useMutation({
    mutationFn: productsApi.createCategory,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['product-categories'] });
      categoryForm.reset();
      setFormError('');
      setEditingCategory(null);
    },
    onError: (error: unknown) => {
      setFormError(getErrorMessage(error, 'Failed to create category'));
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<ProductCategory> }) =>
      productsApi.updateCategory(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['product-categories'] });
      categoryForm.reset();
      setFormError('');
      setEditingCategory(null);
    },
    onError: (error: unknown) => {
      setFormError(getErrorMessage(error, 'Failed to update category'));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: productsApi.deleteCategory,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['product-categories'] });
      setDeleteConfirm(null);
      setFormError('');
    },
    onError: (error: unknown) => {
      setFormError(getErrorMessage(error, 'Failed to delete category'));
    },
  });

  const resetForm = () => {
    setEditingCategory(null);
    setFormError('');
    categoryForm.reset({ name: '', description: '' });
  };

  const startEditCategory = (category: ProductCategory) => {
    setEditingCategory(category);
    setFormError('');
    categoryForm.reset({
      name: category.name,
      description: category.description || '',
    });
  };

  const onCreateCategory = (values: CategoryForm): void => {
    const parsed = categorySchema.safeParse(values);
    if (!parsed.success) {
      setFormError(parsed.error.issues[0]?.message ?? 'Validation failed');
      return;
    }

    if (editingCategory) {
      // Update existing category
      updateMutation.mutate({
        id: editingCategory.id,
        payload: parsed.data,
      });
    } else {
      // Create new category
      categoryMutation.mutate(parsed.data);
    }
  };

  const categories = categoriesQuery.data ?? [];
  const isSaving = categoryMutation.isPending || updateMutation.isPending;

  return (
    <AppLayout title="Product Categories">
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Form Section */}
        <div className="hms-card xl:col-span-1 overflow-hidden">
          <div className="border-b border-neutral-200 px-5 py-4">
            <h2 className="font-display text-lg font-bold text-neutral-900">
              {editingCategory ? 'Modify Category' : 'Add Category'}
            </h2>
          </div>

          <div className="p-5">
            {editingCategory && (
              <div className="flex items-center justify-between mb-4 pb-4 border-b border-neutral-200">
                <h3 className="text-sm font-semibold text-neutral-900">Editing: {editingCategory.name}</h3>
                <button
                  type="button"
                  onClick={resetForm}
                  className="inline-flex items-center gap-1 text-sm text-neutral-500 hover:text-neutral-700 transition"
                >
                  <span className="material-icons text-base" aria-hidden="true">close</span>
                  Clear
                </button>
              </div>
            )}

            <form className="space-y-3" onSubmit={categoryForm.handleSubmit(onCreateCategory)}>
              <div>
                <label htmlFor="category_name" className="hms-label">
                  Category name *
                </label>
                <input
                  id="category_name"
                  className="hms-input"
                  placeholder="Category name"
                  {...categoryForm.register('name')}
                />
              </div>
              <div>
                <label htmlFor="category_description" className="hms-label">
                  Description
                </label>
                <textarea
                  id="category_description"
                  className="hms-input resize-none h-24"
                  placeholder="Description (optional)"
                  {...categoryForm.register('description')}
                />
              </div>

              {formError && <p className="text-sm text-danger">{formError}</p>}
              {categoryMutation.isSuccess && (
                <p className="text-sm text-success">Category created successfully</p>
              )}
              {updateMutation.isSuccess && (
                <p className="text-sm text-success">Category updated successfully</p>
              )}

              <button
                type="submit"
                disabled={isSaving}
                className="w-full rounded-lg bg-primary px-5 py-2.5 text-sm font-bold text-white shadow-lg shadow-primary/20 transition hover:bg-primary/90 disabled:opacity-60"
              >
                {isSaving ? 'Saving...' : editingCategory ? 'Update Category' : 'Create Category'}
              </button>
            </form>
          </div>
        </div>

        {/* Table Section */}
        <div className="hms-card xl:col-span-2 overflow-hidden">
          <div className="border-b border-neutral-200 px-5 py-4">
            <h2 className="font-display text-lg font-bold text-neutral-900">Categories</h2>
          </div>
          <div className="p-5">
            {categoriesQuery.isLoading && <PageLoading message="Loading categories..." />}
            {categoriesQuery.isError && <PageError message="Failed to load categories" />}
            {!categoriesQuery.isLoading &&
              !categoriesQuery.isError &&
              categories.length === 0 && <PageEmpty message="No categories found. Create one to get started." />}
            {!categoriesQuery.isLoading &&
              !categoriesQuery.isError &&
              categories.length > 0 && (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <caption className="sr-only">Product categories list</caption>
                    <thead className="bg-neutral-50">
                      <tr className="text-left border-y border-neutral-200">
                        <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">
                          Name
                        </th>
                        <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">
                          Description
                        </th>
                        <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">
                          Actions
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-neutral-100">
                      {categories.map((category) => (
                        <tr key={category.id} className="hover:bg-neutral-50/80">
                          <td className="px-4 py-3 font-medium">{category.name}</td>
                          <td className="px-4 py-3 text-neutral-600">{category.description || '—'}</td>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <button
                                type="button"
                                onClick={() => startEditCategory(category)}
                                className="rounded px-2 py-1 text-xs font-semibold text-primary hover:bg-primary/10 transition"
                              >
                                Modify
                              </button>
                              <button
                                type="button"
                                onClick={() => setDeleteConfirm(category)}
                                className="rounded px-2 py-1 text-xs font-semibold text-danger hover:bg-red-50 transition"
                              >
                                Delete
                              </button>
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

      {/* Delete Confirmation Modal */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
          <div className="hms-card w-full max-w-md space-y-6 p-6">
            <div>
              <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-red-100">
                <span className="material-icons text-red-600 text-2xl" aria-hidden="true">
                  delete
                </span>
              </div>
              <h2 className="font-display text-lg font-bold text-neutral-900">Delete Category</h2>
              <p className="mt-2 text-sm text-neutral-600">
                Are you sure you want to delete <strong>{deleteConfirm.name}</strong>? This action cannot be undone.
              </p>

              {deleteMutation.isError && formError && (
                <div className="mt-4 rounded-lg bg-red-50 border border-red-200 p-4">
                  <div className="flex items-start gap-3">
                    <span className="material-icons text-red-600 text-lg flex-shrink-0" aria-hidden="true">
                      error
                    </span>
                    <p className="text-sm text-red-800 font-medium">{formError}</p>
                  </div>
                </div>
              )}

              {deleteMutation.isPending && (
                <div className="mt-4 flex items-center gap-3 text-sm text-neutral-600">
                  <span className="material-icons animate-spin">progress_activity</span>
                  Deleting category...
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
              <button
                type="button"
                onClick={() => deleteMutation.mutate(deleteConfirm.id)}
                disabled={deleteMutation.isPending}
                className="flex-1 rounded-lg bg-red-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-red-600/20 transition hover:bg-red-700 disabled:opacity-50"
              >
                <span className="material-icons text-sm align-middle mr-1">delete</span>
                {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </AppLayout>
  );
};

export default CategoriesPage;
