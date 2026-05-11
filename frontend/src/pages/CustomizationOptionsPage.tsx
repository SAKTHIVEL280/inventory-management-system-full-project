import { useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AppLayout } from '../components/AppLayout';
import { customizationOptionsApi } from '../api/customizationOptions';
import { PageEmpty, PageError, PageLoading } from '../components/PageState';
import { confirmWithToast, showError, showSuccess } from '../utils/toastHelper';
import type { CustomizationOption, CustomizationOptionPayload } from '../types';

const MODULE_OPTIONS = [
  { value: 'customer', label: 'Customer' },
  { value: 'supplier', label: 'Supplier' },
  { value: 'rdn', label: 'RDN' },
];

const FIELD_OPTIONS: Record<string, string[]> = {
  customer: ['country', 'currency', 'state'],
  supplier: ['country', 'currency', 'state'],
  rdn: ['return_reason'],
};

const schema = z.object({
  module: z.string().min(1, 'Module is required'),
  field_name: z.string().min(1, 'Field is required'),
  option_value: z.string().min(1, 'Option value is required'),
  display_label: z.string().optional().nullable(),
  sort_order: z.coerce.number().int().min(0, 'Sort order must be 0 or more').default(0),
  is_active: z.boolean().default(true),
});

type CustomizationFormValues = z.infer<typeof schema>;

const DEFAULT_VALUES: CustomizationFormValues = {
  module: '',
  field_name: '',
  option_value: '',
  display_label: '',
  sort_order: 0,
  is_active: true,
};

const CustomizationOptionsPage = () => {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [moduleFilter, setModuleFilter] = useState('');
  const [fieldFilter, setFieldFilter] = useState('');
  const [includeInactive, setIncludeInactive] = useState(false);
  const [editingOption, setEditingOption] = useState<CustomizationOption | null>(null);

  const listQuery = useQuery({
    queryKey: ['customization-options', moduleFilter, fieldFilter, search, includeInactive],
    queryFn: () => customizationOptionsApi.list({
      module: moduleFilter || undefined,
      field_name: fieldFilter || undefined,
      search: search || undefined,
      include_inactive: includeInactive,
      page: 1,
      page_size: 500,
    }),
  });

  const form = useForm<CustomizationFormValues>({
    resolver: zodResolver(schema),
    defaultValues: DEFAULT_VALUES,
  });

  const { register, handleSubmit, reset, watch, formState } = form;
  const watchedModule = watch('module');
  const fieldOptions = FIELD_OPTIONS[watchedModule] || [];

  const resetForm = () => {
    setEditingOption(null);
    reset(DEFAULT_VALUES);
  };

  const createMutation = useMutation({
    mutationFn: (payload: CustomizationOptionPayload) => customizationOptionsApi.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customization-options'] });
      resetForm();
      showSuccess('Customization option created');
    },
    onError: (error: unknown) => {
      showError((error as { message?: string })?.message || 'Failed to create option');
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Partial<CustomizationOptionPayload> }) =>
      customizationOptionsApi.update(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customization-options'] });
      resetForm();
      showSuccess('Customization option updated');
    },
    onError: (error: unknown) => {
      showError((error as { message?: string })?.message || 'Failed to update option');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => customizationOptionsApi.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['customization-options'] });
      showSuccess('Customization option deleted');
    },
    onError: (error: unknown) => {
      showError((error as { message?: string })?.message || 'Failed to delete option');
    },
  });

  const onSubmit = (values: CustomizationFormValues) => {
    const payload: CustomizationOptionPayload = {
      module: values.module.trim(),
      field_name: values.field_name.trim(),
      option_value: values.option_value.trim(),
      display_label: values.display_label?.trim() || undefined,
      sort_order: Number(values.sort_order || 0),
      is_active: values.is_active,
    };

    if (editingOption) {
      updateMutation.mutate({ id: editingOption.id, payload });
    } else {
      createMutation.mutate(payload);
    }
  };

  const startEdit = (option: CustomizationOption) => {
    setEditingOption(option);
    reset({
      module: option.module,
      field_name: option.field_name,
      option_value: option.option_value,
      display_label: option.display_label || '',
      sort_order: option.sort_order,
      is_active: option.is_active,
    });
  };

  const handleDelete = async (option: CustomizationOption) => {
    await confirmWithToast(`Delete option "${option.display_label || option.option_value}"?`, {
      type: 'danger',
      onConfirm: () => deleteMutation.mutateAsync(option.id),
    });
  };

  const items = listQuery.data?.items ?? [];
  const isSaving = createMutation.isPending || updateMutation.isPending;

  const moduleFilterOptions = useMemo(() => MODULE_OPTIONS, []);
  const fieldFilterOptions = useMemo(() => FIELD_OPTIONS[moduleFilter] || [], [moduleFilter]);

  return (
    <AppLayout title="Customization Options">
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="hms-card p-5 lg:col-span-1">
          <div className="flex items-center justify-between">
            <h2 className="font-display text-lg font-bold text-neutral-900">
              {editingOption ? 'Edit Option' : 'Add Option'}
            </h2>
            {editingOption && (
              <button type="button" onClick={resetForm} className="text-sm text-neutral-500 hover:text-neutral-700">
                Cancel
              </button>
            )}
          </div>

          <form className="mt-4 space-y-3" onSubmit={handleSubmit(onSubmit)}>
            <div>
              <label className="hms-label">Module *</label>
              <input
                list="customization-module-options"
                className="hms-input"
                placeholder="Module"
                {...register('module')}
              />
              <datalist id="customization-module-options">
                {MODULE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </datalist>
              {formState.errors.module && (
                <p className="mt-1 text-xs text-red-500">{formState.errors.module.message}</p>
              )}
            </div>
            <div>
              <label className="hms-label">Field *</label>
              <input
                list="customization-field-options"
                className="hms-input"
                placeholder="Field"
                {...register('field_name')}
              />
              <datalist id="customization-field-options">
                {fieldOptions.map((field) => (
                  <option key={field} value={field} />
                ))}
              </datalist>
              {formState.errors.field_name && (
                <p className="mt-1 text-xs text-red-500">{formState.errors.field_name.message}</p>
              )}
            </div>
            <div>
              <label className="hms-label">Option Value *</label>
              <input className="hms-input" placeholder="Option value" {...register('option_value')} />
              {formState.errors.option_value && (
                <p className="mt-1 text-xs text-red-500">{formState.errors.option_value.message}</p>
              )}
            </div>
            <div>
              <label className="hms-label">Display Label</label>
              <input className="hms-input" placeholder="Display label" {...register('display_label')} />
            </div>
            <div>
              <label className="hms-label">Sort Order</label>
              <input type="number" min="0" className="hms-input" {...register('sort_order')} />
              {formState.errors.sort_order && (
                <p className="mt-1 text-xs text-red-500">{formState.errors.sort_order.message}</p>
              )}
            </div>
            <label className="flex items-center gap-2 text-sm text-neutral-600">
              <input type="checkbox" className="h-4 w-4" {...register('is_active')} />
              Active
            </label>

            <button
              type="submit"
              disabled={isSaving}
              className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-bold text-white shadow-lg shadow-primary/20 disabled:opacity-50"
            >
              {isSaving ? 'Saving...' : editingOption ? 'Update Option' : 'Create Option'}
            </button>
          </form>
        </div>

        <div className="hms-card overflow-hidden lg:col-span-2">
          <div className="border-b border-neutral-200 px-5 py-4">
            <h2 className="font-display text-lg font-bold text-neutral-900">Options</h2>
          </div>
          <div className="p-5">
            <div className="mb-4 flex flex-wrap gap-3">
              <input
                type="text"
                className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm"
                placeholder="Search options"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
              <select
                className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm"
                value={moduleFilter}
                onChange={(event) => {
                  setModuleFilter(event.target.value);
                  setFieldFilter('');
                }}
              >
                <option value="">All Modules</option>
                {moduleFilterOptions.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
              <select
                className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm"
                value={fieldFilter}
                onChange={(event) => setFieldFilter(event.target.value)}
                disabled={!moduleFilter}
              >
                <option value="">All Fields</option>
                {fieldFilterOptions.map((field) => (
                  <option key={field} value={field}>{field}</option>
                ))}
              </select>
              <label className="flex items-center gap-2 text-sm text-neutral-600">
                <input
                  type="checkbox"
                  className="h-4 w-4"
                  checked={includeInactive}
                  onChange={(event) => setIncludeInactive(event.target.checked)}
                />
                Include inactive
              </label>
            </div>

            {listQuery.isLoading && <PageLoading message="Loading options..." />}
            {listQuery.isError && <PageError message="Failed to load customization options" />}
            {!listQuery.isLoading && !listQuery.isError && items.length === 0 && (
              <PageEmpty message="No customization options found" />
            )}
            {!listQuery.isLoading && !listQuery.isError && items.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-neutral-50">
                    <tr className="text-left border-y border-neutral-200">
                      <th className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Module</th>
                      <th className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Field</th>
                      <th className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Value</th>
                      <th className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Label</th>
                      <th className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Sort</th>
                      <th className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Status</th>
                      <th className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-100">
                    {items.map((option) => (
                      <tr key={option.id} className="hover:bg-neutral-50/80">
                        <td className="px-4 py-3 font-medium">{option.module}</td>
                        <td className="px-4 py-3">{option.field_name}</td>
                        <td className="px-4 py-3">{option.option_value}</td>
                        <td className="px-4 py-3">{option.display_label || '-'}</td>
                        <td className="px-4 py-3">{option.sort_order}</td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${option.is_active ? 'bg-green-100 text-green-700' : 'bg-neutral-100 text-neutral-600'}`}>
                            {option.is_active ? 'Active' : 'Inactive'}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => startEdit(option)}
                              className="rounded px-2 py-1 text-xs font-medium text-primary hover:bg-primary/10"
                            >
                              Edit
                            </button>
                            <button
                              onClick={() => handleDelete(option)}
                              className="rounded px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50"
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
    </AppLayout>
  );
};

export default CustomizationOptionsPage;
