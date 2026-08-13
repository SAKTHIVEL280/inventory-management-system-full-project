// Small, dependency-free CSV export helper. Triggers a client-side download of
// the given rows. A UTF-8 BOM is prepended so Excel opens non-ASCII correctly.

type Cell = string | number | null | undefined;

const escapeCell = (value: Cell): string => {
  const text = value === null || value === undefined ? '' : String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
};

export function exportToCsv(filename: string, headers: string[], rows: Cell[][]): void {
  const lines = [headers, ...rows].map((row) => row.map(escapeCell).join(','));
  const csv = '﻿' + lines.join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

/** Timestamp suffix (YYYY-MM-DD) for export filenames. */
export const csvDateStamp = (): string => new Date().toISOString().slice(0, 10);
