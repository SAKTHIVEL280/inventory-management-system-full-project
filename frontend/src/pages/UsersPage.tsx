import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { usersApi } from '../api/users';
import { UserCreateRequest, UserManagement } from '../types';
import { AppLayout } from '../components/AppLayout';
import { PageEmpty, PageError, PageLoading } from '../components/PageState';

const schema = z.object({
  full_name: z.string().min(1, 'Name is required'),
  email: z.string().email('Valid email required'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
  role: z.enum(['admin', 'accounting', 'sales', 'inventory']),
});

type UserForm = z.infer<typeof schema>;

const roleClassMap: Record<string, string> = {
  admin: 'bg-role-admin',
  accounting: 'bg-role-accounting',
  sales: 'bg-role-sales',
  inventory: 'bg-role-inventory',
};

const UsersPage = () => {
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState('');

  const { data, isLoading, isError } = useQuery({
    queryKey: ['users'],
    queryFn: usersApi.list,
  });

  const { register, handleSubmit, reset } = useForm<UserForm>({
    defaultValues: {
      full_name: '',
      email: '',
      password: '',
      role: 'inventory',
    },
  });

  const createMutation = useMutation({
    mutationFn: (payload: UserCreateRequest) => usersApi.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      reset();
      setFormError('');
    },
  });

  const onSubmit = (values: UserForm): void => {
    const parsed = schema.safeParse(values);
    if (!parsed.success) {
      setFormError(parsed.error.issues[0]?.message ?? 'Validation failed');
      return;
    }

    createMutation.mutate({
      ...parsed.data,
      is_active: true,
      permission_overrides: { allow: [], deny: [] },
    });
  };

  const items: UserManagement[] = data?.items ?? [];

  return (
    <AppLayout title="User Management">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="hms-card lg:col-span-1 p-5">
          <h2 className="font-display text-lg font-bold text-neutral-900 mb-4">New User</h2>
          <form className="space-y-3" onSubmit={handleSubmit(onSubmit)}>
            <label htmlFor="full_name" className="hms-label">Full name</label>
            <input id="full_name" className="hms-input" placeholder="Full name" {...register('full_name')} />
            <label htmlFor="email" className="hms-label">Email</label>
            <input id="email" className="hms-input" placeholder="Email" autoComplete="email" {...register('email')} />
            <label htmlFor="password" className="hms-label">Temporary password</label>
            <input id="password" type="password" className="hms-input" placeholder="Temporary password" autoComplete="new-password" {...register('password')} />
            <label htmlFor="role" className="hms-label">Role</label>
            <select id="role" className="hms-input" {...register('role')}>
              <option value="admin">Admin</option>
              <option value="accounting">Accounting</option>
              <option value="sales">Sales</option>
              <option value="inventory">Inventory</option>
            </select>
            {formError && <p className="text-sm text-danger" role="alert" aria-live="assertive">{formError}</p>}
            {createMutation.isError && <p className="text-sm text-danger" role="alert" aria-live="assertive">Failed to create user</p>}
            {createMutation.isSuccess && <p className="text-sm text-success" role="status" aria-live="polite">User created successfully</p>}
            <button type="submit" disabled={createMutation.isPending} className="w-full rounded-lg bg-primary px-5 py-2.5 text-sm font-bold text-white shadow-lg shadow-primary/20 transition hover:bg-primary/90 disabled:opacity-60">
              {createMutation.isPending ? 'Saving...' : 'Create User'}
            </button>
          </form>
        </div>

        <div className="hms-card lg:col-span-2 overflow-hidden">
          <div className="border-b border-neutral-200 px-5 py-4">
            <h2 className="font-display text-lg font-bold text-neutral-900">Users</h2>
          </div>
          <div className="p-5">
          {isLoading && <PageLoading message="Loading users..." />}
          {isError && <PageError message="Failed to load users" />}
          {!isLoading && !isError && items.length === 0 && <PageEmpty message="No users found" />}
          {!isLoading && !isError && items.length > 0 && (
            <table className="w-full text-sm">
              <caption className="sr-only">User accounts list</caption>
              <thead className="bg-neutral-50">
                <tr className="text-left border-y border-neutral-200">
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Name</th>
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Email</th>
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Role</th>
                  <th scope="col" className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {items.map((user) => (
                  <tr key={user.id} className="hover:bg-neutral-50/80">
                    <td className="px-4 py-3">{user.full_name}</td>
                    <td className="px-4 py-3">{user.email}</td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2.5 py-1 text-xs font-bold uppercase tracking-wide text-white ${roleClassMap[user.role] ?? 'bg-primary'}`}>
                        {user.role}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2.5 py-1 text-xs font-bold uppercase tracking-wide ${user.is_active ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-600'}`}>
                        {user.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          </div>
        </div>
      </div>
    </AppLayout>
  );
};

export default UsersPage;
