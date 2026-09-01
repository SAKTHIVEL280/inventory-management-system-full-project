// Trigger a browser download for a binary response (e.g. an .xlsx blob returned by
// an authenticated API call with `responseType: 'blob'`).
export function downloadBlob(data: BlobPart, filename: string, mime?: string): void {
  const blob = mime ? new Blob([data], { type: mime }) : new Blob([data]);
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  window.URL.revokeObjectURL(url);
  link.remove();
}

/** YYYY-MM-DD stamp for export filenames. */
export const fileDateStamp = (): string => new Date().toISOString().slice(0, 10);
