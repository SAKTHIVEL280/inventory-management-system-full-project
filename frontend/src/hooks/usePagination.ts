/**
 * usePagination — shared pagination state, standardized across the ERP.
 *
 * Mirrors the Sales Invoice pagination behaviour:
 *  - Rows per page: 20 / 50 / 100 / All (default 20).
 *  - "All" shows every record for the current filters.
 *  - Auto-resets to page 1 when filters/search change or the page size changes.
 *  - Provides both CLIENT-side slicing (`paginate`) and SERVER-side `offset/limit`.
 */
import { useEffect, useMemo, useState } from 'react';

export type PageSize = number | 'all';

export const PAGE_SIZE_OPTIONS: PageSize[] = [20, 50, 100, 'all'];
export const DEFAULT_PAGE_SIZE = 20;

export function usePagination(resetKey?: unknown, initial: PageSize = DEFAULT_PAGE_SIZE) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<PageSize>(initial);

  // Reset to the first page whenever the filter/search key changes, or the page
  // size changes. `resetKey` should be a stable serialization of the active
  // filters (e.g. JSON.stringify([search, status, dateFrom, dateTo])).
  useEffect(() => {
    setPage(1);
  }, [resetKey, pageSize]);

  const helpers = useMemo(
    () => ({
      totalPages: (total: number) => (pageSize === 'all' ? 1 : Math.max(1, Math.ceil(total / pageSize))),
      rangeStart: (total: number) => (total === 0 ? 0 : pageSize === 'all' ? 1 : (page - 1) * pageSize + 1),
      rangeEnd: (total: number) => (pageSize === 'all' ? total : Math.min(page * pageSize, total)),
      /** Client-side slice of an already-filtered list for the current page. */
      paginate: <T,>(items: T[]): T[] =>
        pageSize === 'all' ? items : items.slice((page - 1) * pageSize, page * pageSize),
      /** Server-side helpers. `limit` is undefined for "All". */
      offset: pageSize === 'all' ? 0 : (page - 1) * pageSize,
      limit: pageSize === 'all' ? undefined : pageSize,
    }),
    [page, pageSize],
  );

  return { page, setPage, pageSize, setPageSize, ...helpers };
}
