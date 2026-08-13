import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AppLayout } from '../components/AppLayout';
import { rdnApi } from '../api/rdn';
import { RDNCreditNoteOverviewTable } from '../components/rdn/RDNCreditNoteOverviewTable';
import { RDNCreditNoteDetailModal } from '../components/rdn/RDNCreditNoteDetailModal';
import { fetchAllPages } from '../utils/fetchAllPages';
import type { RDNCreditNoteDetailResponse } from '../types';

const RDNCreditNotePage = () => {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [detailOpen, setDetailOpen] = useState(false);
  const [selectedCreditNoteId, setSelectedCreditNoteId] = useState<string | null>(null);

  const listQuery = useQuery({
    queryKey: ['rdn-credit-notes', search, statusFilter],
    // Load ALL matching credit notes (chunked) so none are hidden by a page cap.
    queryFn: async () => {
      const { items, total } = await fetchAllPages(async (pageNo, size) => {
        const res = await rdnApi.listCreditNotes({ search: search || undefined, status: statusFilter || undefined, page: pageNo, page_size: size });
        return { items: res.items || [], total: res.total ?? 0 };
      });
      return { items, total, page: 1, page_size: items.length, has_more: false };
    },
  });

  const detailQuery = useQuery({
    queryKey: ['rdn-credit-note-detail', selectedCreditNoteId],
    queryFn: () => rdnApi.getCreditNote(selectedCreditNoteId || ''),
    enabled: Boolean(selectedCreditNoteId),
  });

  const rows = useMemo(() => listQuery.data?.items ?? [], [listQuery.data?.items]);

  const handleSelect = (id: string) => {
    setSelectedCreditNoteId(id);
    setDetailOpen(true);
  };

  const handleCloseDetail = () => {
    setDetailOpen(false);
    setSelectedCreditNoteId(null);
  };

  return (
    <AppLayout title="Return Delivery - Credit Note">
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-3">
            <input
              type="text"
              placeholder="Search by RDN or Invoice number"
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
              <option value="posted">Posted</option>
              <option value="draft">Draft</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>
        </div>

        <RDNCreditNoteOverviewTable
          items={rows}
          loading={listQuery.isLoading}
          onSelect={handleSelect}
        />
      </div>

      <RDNCreditNoteDetailModal
        open={detailOpen}
        creditNote={(detailQuery.data as RDNCreditNoteDetailResponse | undefined)?.credit_note ?? null}
        items={(detailQuery.data as RDNCreditNoteDetailResponse | undefined)?.items ?? []}
        onClose={handleCloseDetail}
      />
    </AppLayout>
  );
};

export default RDNCreditNotePage;
