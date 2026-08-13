import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AppLayout } from '../components/AppLayout';
import { rdnApi } from '../api/rdn';
import { RDNFormModal } from '../components/rdn/RDNFormModal';
import { RDNDetailModal } from '../components/rdn/RDNDetailModal';
import { RDNOverviewTable } from '../components/rdn/RDNOverviewTable';
import { confirmWithToast, showError, showSuccess } from '../utils/toastHelper';
import { usePermissions } from '../hooks/usePermissions';
import { fetchAllPages } from '../utils/fetchAllPages';
import type { RDNDetailResponse } from '../types';

const RDNPage = () => {
  const queryClient = useQueryClient();
  const { isAdmin } = usePermissions();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [detailOpen, setDetailOpen] = useState(false);
  const [selectedRdnId, setSelectedRdnId] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editingData, setEditingData] = useState<RDNDetailResponse | null>(null);

  const listQuery = useQuery({
    queryKey: ['rdn-list', search, statusFilter],
    // Load ALL matching RDNs (chunked) so none are hidden by a page-size cap.
    queryFn: async () => {
      const { items, total } = await fetchAllPages(async (pageNo, size) => {
        const res = await rdnApi.list({ search: search || undefined, status: statusFilter || undefined, page: pageNo, page_size: size });
        return { items: res.items || [], total: res.total ?? 0 };
      });
      return { items, total, page: 1, page_size: items.length, has_more: false };
    },
  });

  const detailQuery = useQuery({
    queryKey: ['rdn-detail', selectedRdnId],
    queryFn: () => rdnApi.get(selectedRdnId || ''),
    enabled: Boolean(selectedRdnId),
  });

  const confirmMutation = useMutation({
    mutationFn: (id: string) => rdnApi.confirm(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rdn-list'] });
      queryClient.invalidateQueries({ queryKey: ['rdn-detail'] });
      showSuccess('RDN confirmed');
    },
    onError: () => showError('Failed to confirm RDN'),
  });

  const cancelMutation = useMutation({
    mutationFn: (id: string) => rdnApi.cancel(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rdn-list'] });
      queryClient.invalidateQueries({ queryKey: ['rdn-detail'] });
      showSuccess('RDN cancelled');
    },
    onError: () => showError('Failed to cancel RDN'),
  });

  const rows = useMemo(() => listQuery.data?.items ?? [], [listQuery.data?.items]);

  const handleSelect = (id: string) => {
    setSelectedRdnId(id);
    setDetailOpen(true);
  };

  const handleCloseDetail = () => {
    setDetailOpen(false);
    setSelectedRdnId(null);
  };

  const handleCreate = () => {
    setEditingData(null);
    setFormOpen(true);
  };

  const handleEdit = () => {
    if (!detailQuery.data) return;
    setEditingData(detailQuery.data);
    setFormOpen(true);
  };

  const handleConfirm = async () => {
    if (!selectedRdnId) return;
    await confirmWithToast('Confirm this RDN? Stock will be added to inventory.', {
      type: 'warning',
      onConfirm: async () => {
        await confirmMutation.mutateAsync(selectedRdnId);
      },
    });
  };

  const handleCancel = async () => {
    if (!selectedRdnId) return;
    await confirmWithToast('Cancel this RDN?', {
      type: 'danger',
      onConfirm: async () => {
        await cancelMutation.mutateAsync(selectedRdnId);
      },
    });
  };

  const handleSaved = () => {
    queryClient.invalidateQueries({ queryKey: ['rdn-list'] });
    if (selectedRdnId) {
      queryClient.invalidateQueries({ queryKey: ['rdn-detail', selectedRdnId] });
    }
  };

  return (
    <AppLayout title="Return Delivery Note">
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <input
              type="text"
              placeholder="Search by RDN number"
              className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
            <select
              className="rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm"
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
            >
              <option value="">All Status</option>
              <option value="draft">Draft</option>
              <option value="confirmed">Confirmed</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>
          <button
            onClick={handleCreate}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-primary/20"
          >
            Create New RDN
          </button>
        </div>

        <RDNOverviewTable
          items={rows}
          loading={listQuery.isLoading}
          onSelect={handleSelect}
        />
      </div>

      <RDNFormModal
        open={formOpen}
        initialData={editingData}
        onClose={() => setFormOpen(false)}
        onSaved={handleSaved}
      />

      <RDNDetailModal
        open={detailOpen}
        rdn={detailQuery.data?.rdn ?? null}
        items={detailQuery.data?.items ?? []}
        onClose={handleCloseDetail}
        onConfirm={handleConfirm}
        onCancel={handleCancel}
        onEdit={handleEdit}
        canConfirm={isAdmin}
      />
    </AppLayout>
  );
};

export default RDNPage;
