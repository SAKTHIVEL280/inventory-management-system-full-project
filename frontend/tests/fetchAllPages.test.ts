import { describe, it, expect, vi } from 'vitest';
import { fetchAllPages } from '../src/utils/fetchAllPages';

describe('fetchAllPages', () => {
  it('collects every record across multiple full pages (no truncation)', async () => {
    // 1200 records, chunk 500 -> pages of 500, 500, 200.
    const all = Array.from({ length: 1200 }, (_, i) => ({ id: i }));
    const fetcher = vi.fn(async (page: number, size: number) => ({
      items: all.slice((page - 1) * size, page * size),
      total: all.length,
    }));

    const res = await fetchAllPages(fetcher, 500);

    expect(res.items).toHaveLength(1200);
    expect(res.total).toBe(1200);
    expect(fetcher).toHaveBeenCalledTimes(3); // stops on the partial last page
    // no duplicates / all ids present
    expect(new Set(res.items.map((x) => x.id)).size).toBe(1200);
  });

  it('handles an empty result set', async () => {
    const fetcher = vi.fn(async () => ({ items: [], total: 0 }));
    const res = await fetchAllPages(fetcher, 500);
    expect(res.items).toHaveLength(0);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it('stops on a partial page even when total is not provided', async () => {
    // Endpoint returns no reliable total; a short page signals the end.
    const fetcher = vi.fn(async (page: number, size: number) => ({
      items: page === 1 ? Array.from({ length: size }, (_, i) => ({ id: i }))
                         : [{ id: 999 }],
      total: 0,
    }));
    const res = await fetchAllPages(fetcher, 10);
    expect(res.items).toHaveLength(11);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});
