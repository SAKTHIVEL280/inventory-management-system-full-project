/**
 * fetchAllPages — the "All" option helper for SERVER-paginated lists.
 *
 * Loops through a paginated API in chunks (default 500) and collects every record
 * for the current filters, without hardcoding a page-size ceiling — the same
 * approach the Sales Invoice module uses for its "All" option. Keeps the API
 * tenant-scoped (the caller's fetcher already carries the auth/tenant context).
 */
export async function fetchAllPages<T>(
  fetcher: (page: number, pageSize: number) => Promise<{ items: T[]; total: number }>,
  chunk = 500,
): Promise<{ items: T[]; total: number }> {
  const collected: T[] = [];
  let current = 1;
  let total = 0;
  for (;;) {
    const res = await fetcher(current, chunk);
    const batch = res.items || [];
    collected.push(...batch);
    // Prefer the server's `total` when provided, else fall back to the count so far.
    total = res.total && res.total > 0 ? res.total : collected.length;
    // Stop on a partial/empty page (last page) — robust even when an endpoint does
    // not return a reliable `total`. Also stop once the reported total is reached.
    if (batch.length < chunk) break;
    if (res.total && res.total > 0 && collected.length >= res.total) break;
    current += 1;
    if (current > 10000) break; // hard safety valve
  }
  return { items: collected, total };
}
