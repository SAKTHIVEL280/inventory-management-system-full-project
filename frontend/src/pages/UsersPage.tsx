import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { usersApi, deleteUser } from '../api/users';
import { UserCreateRequest, UserUpdateRequest, UserManagement, ROLE_LABELS, ROLE_BADGE_CLASS } from '../types';
import { AppLayout } from '../components/AppLayout';
import { PageEmpty, PageError, PageLoading } from '../components/PageState';
import { getApiDetail, getApiDetailMessage } from '../utils/apiError';
import { useSubscription } from '../hooks/useSubscription';

const schema = z.object({
  full_name: z.string().min(1, 'Name is required'),
  email: z.string().email('Valid email required'),
  password: z.string().optional(),
  // Assignable BRD roles (the actual options are further restricted to the
  // tenant's plan in the picker below).
  role: z.enum(['admin', 'basic', 'accounts', 'inventory', 'management', 'hr']),
});

type UserForm = z.infer<typeof schema>;

const UsersPage = () => {
  const queryClient = useQueryClient();
  const [formError, setFormError] = useState('');
  const [editingUser, setEditingUser] = useState<UserManagement | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);

  // Plan-gated role availability (BRD §5.5/§6). Only roles included in the tenant's
  // current plan are offered; the backend enforces the same rule authoritatively.
  const { rolesCatalog, atUserLimit, userLimit, activeUserCount, plan } = useSubscription();
  const availableRoles = rolesCatalog.filter((r) => r.available).map((r) => r.role);
  const defaultRole = (availableRoles[0] ?? 'basic') as UserForm['role'];

  const { data, isLoading, isError } = useQuery({
    queryKey: ['users'],
    queryFn: usersApi.list,
  });

  const { register, handleSubmit, reset, setValue } = useForm<UserForm>({
    defaultValues: {
      full_name: '',
      email: '',
      password: '',
      role: defaultRole,
    },
  });

  // Roles shown in the picker: the plan-available roles, plus 'admin' only when
  // editing the existing Tenant Admin (so its role is never silently changed).
  const roleOptions = (() => {
    const opts = [...availableRoles];
    if (editingUser?.role === 'admin' && !opts.includes('admin')) opts.unshift('admin');
    if (opts.length === 0) opts.push(defaultRole);
    return opts;
  })();

  const createMutation = useMutation({
    mutationFn: (payload: UserCreateRequest) => usersApi.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      resetForm();
    },
    onError: (error: unknown) => {
      const detail = getApiDetail(error);
      setFormError(getApiDetailMessage(detail, 'Failed to create user'));
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UserUpdateRequest }) => usersApi.update(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      resetForm();
    },
    onError: (error: unknown) => {
      const detail = getApiDetail(error);
      setFormError(getApiDetailMessage(detail, 'Failed to update user'));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteUser(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      setDeleteConfirm(null);
    },
  });

  const toggleActiveMutation = useMutation({
    mutationFn: ({ user }: { user: UserManagement }) =>
      usersApi.update(user.id, {
        full_name: user.full_name,
        email: user.email,
        role: user.role,
        is_active: !user.is_active,
        permission_overrides: user.permission_overrides as { allow: string[]; deny: string[] } | null ?? { allow: [], deny: [] },
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
    },
  });

  const resetForm = () => {
    setEditingUser(null);
    setFormError('');
    setShowPassword(false);
    reset({ full_name: '', email: '', password: '', role: defaultRole });
  };

  const startEdit = (user: UserManagement) => {
    setEditingUser(user);
    setFormError('');
    setShowPassword(false);
    setValue('full_name', user.full_name);
    setValue('email', user.email);
    setValue('role', user.role);
    setValue('password', '');
  };

  const onSubmit = (values: UserForm): void => {
    const parsed = schema.safeParse(values);
    if (!parsed.success) {
      setFormError(parsed.error.issues[0]?.message ?? 'Validation failed');
      return;
    }

    if (editingUser) {
      updateMutation.mutate({
        id: editingUser.id,
        payload: {
          full_name: parsed.data.full_name,
          email: parsed.data.email,
          password: parsed.data.password || undefined,
          role: parsed.data.role,
          is_active: editingUser.is_active,
          permission_overrides: editingUser.permission_overrides as { allow: string[]; deny: string[] } | null ?? { allow: [], deny: [] },
        },
      });
    } else {
      if (!parsed.data.password || parsed.data.password.length < 8) {
        setFormError('Password must be at least 8 characters');
        return;
      }
      createMutation.mutate({
        full_name: parsed.data.full_name,
        email: parsed.data.email,
        password: parsed.data.password,
        role: parsed.data.role,
        is_active: true,
        permission_overrides: { allow: [], deny: [] },
      });
    }
  };

  const items: UserManagement[] = data?.items ?? [];
  const isSaving = createMutation.isPending || updateMutation.isPending;

  return (
    <AppLayout title="User Management">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="hms-card lg:col-span-1 p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-display text-lg font-bold text-neutral-900">
              {editingUser ? 'Modify/Change User' : 'New User'}
            </h2>
            {editingUser && (
              <button type="button" onClick={resetForm} className="text-sm text-neutral-500 hover:text-neutral-700">
                Cancel
              </button>
            )}
          </div>
          <form className="space-y-3" onSubmit={handleSubmit(onSubmit)}>
            <div>
              <label htmlFor="full_name" className="hms-label">Full name</label>
              <input id="full_name" className="hms-input" placeholder="Full name" {...register('full_name')} />
            </div>
            <div>
              <label htmlFor="email" className="hms-label">Email</label>
              <input id="email" className="hms-input" placeholder="Email" autoComplete="email" {...register('email')} />
            </div>
            <div>
              <label htmlFor="password" className="hms-label">
                {editingUser ? 'New password (leave blank to keep)' : 'Set Password'}
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  className="hms-input pr-10"
                  placeholder={editingUser ? 'Leave blank to keep current' : 'Set password'}
                  autoComplete="new-password"
                  {...register('password')}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((prev) => !prev)}
                  className="absolute inset-y-0 right-0 flex items-center px-3 text-neutral-500 hover:text-neutral-700"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  <span className="material-icons text-base" aria-hidden="true">
                    {showPassword ? 'visibility_off' : 'visibility'}
                  </span>
                </button>
              </div>
            </div>
            <div>
              <label htmlFor="role" className="hms-label">Role</label>
              <select id="role" className="hms-input" {...register('role')}>
                {roleOptions.map((r) => (
                  <option key={r} value={r}>{ROLE_LABELS[r] ?? r}</option>
                ))}
              </select>
              {plan && (
                <p className="mt-1 text-xs text-neutral-500">
                  Roles available on your {plan} plan. Upgrade to unlock more.
                </p>
              )}
            </div>
            {!editingUser && atUserLimit && (
              <p className="text-sm text-amber-600" role="alert">
                User limit reached ({activeUserCount}/{userLimit} on {plan}). Deactivate a user or upgrade your plan to add more.
              </p>
            )}
            {formError && <p className="text-sm text-danger" role="alert" aria-live="assertive">{formError}</p>}
            <button
              type="submit"
              disabled={isSaving || (!editingUser && atUserLimit)}
              className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-bold text-white shadow-lg shadow-primary/20 transition hover:bg-primary/90 disabled:opacity-50"
            >
              {isSaving ? 'Saving...' : editingUser ? 'Modify/Change User' : 'Create User'}
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
            <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <caption className="sr-only">User accounts list</caption>
              <thead className="bg-neutral-50">
                <tr className="text-left border-y border-neutral-200">
                  <th scope="col" className="whitespace-nowrap px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Name</th>
                  <th scope="col" className="whitespace-nowrap px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Email</th>
                  <th scope="col" className="whitespace-nowrap px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Role</th>
                  <th scope="col" className="whitespace-nowrap px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Status</th>
                  <th scope="col" className="whitespace-nowrap px-4 py-3 text-xs font-bold uppercase tracking-wider text-neutral-500">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {items.map((user) => (
                  <tr key={user.id} className="hover:bg-neutral-50/80">
                    <td className="px-4 py-3 align-middle font-medium">{user.full_name}</td>
                    <td className="px-4 py-3 align-middle break-all">{user.email}</td>
                    <td className="px-4 py-3 align-middle">
                      <span className={`inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-bold uppercase tracking-wide text-white ${ROLE_BADGE_CLASS[user.role] ?? 'bg-primary'}`}>
                        {ROLE_LABELS[user.role] ?? user.role}
                      </span>
                    </td>
                    <td className="px-4 py-3 align-middle">
                      <span className={`inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-bold uppercase tracking-wide ${user.is_active ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-600'}`}>
                        {user.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="px-4 py-3 align-middle">
                      <div className="flex items-center gap-2 whitespace-nowrap">
                        <button
                          type="button"
                          onClick={() => startEdit(user)}
                          className="rounded px-2 py-1 text-xs font-semibold text-primary hover:bg-primary/10 transition"
                          title="Modify/Change user"
                        >
                          Modify/Change
                        </button>
                        <button
                          type="button"
                          onClick={() => toggleActiveMutation.mutate({ user })}
                          className={`rounded px-2 py-1 text-xs font-semibold transition ${user.is_active ? 'text-amber-600 hover:bg-amber-50' : 'text-green-600 hover:bg-green-50'}`}
                          title={user.is_active ? 'Deactivate' : 'Activate'}
                        >
                          {user.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                        <button
                          type="button"
                          onClick={() => setDeleteConfirm(user.id)}
                          className="rounded px-2 py-1 text-xs font-semibold text-danger hover:bg-red-50 transition"
                          title="Delete user"
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
          <div className="hms-card w-full max-w-sm space-y-6 p-6">
            <div>
              <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-red-100">
                <span className="material-icons text-red-600" aria-hidden="true">person_remove</span>
              </div>
              <h2 className="font-display text-lg font-bold text-neutral-900">Delete User</h2>
              <p className="mt-2 text-sm text-neutral-600">
                Are you sure you want to delete this user? This action cannot be undone.
              </p>
            </div>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setDeleteConfirm(null)}
                className="flex-1 rounded-lg border border-neutral-200 bg-white px-4 py-2.5 text-sm font-semibold text-neutral-600 transition hover:bg-neutral-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  deleteMutation.mutate(deleteConfirm);
                }}
                className="flex-1 rounded-lg bg-red-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-red-600/20 transition hover:bg-red-700"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </AppLayout>
  );
};

export default UsersPage;
