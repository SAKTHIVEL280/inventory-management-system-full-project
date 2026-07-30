/**
 * PaginationControls — the single, shared pagination UI for the whole ERP.
 *
 * This is the exact "Rows per page (20/50/100/All) + Showing X-Y of Z + Prev/Next"
 * control used by the Sales Invoice module, extracted so every paginated module
 * looks and behaves identically.
 */
import type { PageSize } from '../hooks/usePagination';

interface PaginationControlsProps {
  page: number;
  pageSize: PageSize;
  total: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: PageSize) => void;
  /** Plural noun for the empty message, e.g. "invoices", "payments", "records". */
  entityLabel?: string;
  /** Hide the top border (when embedded somewhere that already has one). */
  noBorder?: boolean;
}

export function PaginationControls({
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
  entityLabel = 'records',
  noBorder = false,
}: PaginationControlsProps) {
  const totalPages = pageSize === 'all' ? 1 : Math.max(1, Math.ceil(total / pageSize));
  const rangeStart = total === 0 ? 0 : pageSize === 'all' ? 1 : (page - 1) * pageSize + 1;
  const rangeEnd = pageSize === 'all' ? total : Math.min(page * pageSize, total);

  return (
    <div
      className={`flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-xs text-neutral-600 ${
        noBorder ? '' : 'border-t border-neutral-200'
      }`}
    >
      <div className="flex items-center gap-2">
        <span className="font-medium">Rows per page</span>
        <select
          className="rounded border border-neutral-200 bg-white px-2 py-1 text-xs"
          value={pageSize === 'all' ? 'all' : String(pageSize)}
          onChange={(e) => onPageSizeChange(e.target.value === 'all' ? 'all' : Number(e.target.value))}
        >
          <option value="20">20</option>
          <option value="50">50</option>
          <option value="100">100</option>
          <option value="all">All</option>
        </select>
        <span className="text-neutral-500">
          {total === 0 ? `No ${entityLabel}` : `Showing ${rangeStart}-${rangeEnd} of ${total}`}
        </span>
      </div>
      {pageSize !== 'all' && (
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => onPageChange(Math.max(1, page - 1))}
            disabled={page <= 1}
            className="rounded border border-neutral-200 bg-white px-3 py-1 font-semibold text-neutral-700 disabled:cursor-not-allowed disabled:opacity-40 hover:bg-neutral-50"
          >
            Previous
          </button>
          <span className="font-medium">Page {page} of {totalPages}</span>
          <button
            type="button"
            onClick={() => onPageChange(Math.min(totalPages, page + 1))}
            disabled={page >= totalPages}
            className="rounded border border-neutral-200 bg-white px-3 py-1 font-semibold text-neutral-700 disabled:cursor-not-allowed disabled:opacity-40 hover:bg-neutral-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
