/**
 * Action Logs Page
 * Dedicated page for viewing and filtering system action logs.
 */
import { useEffect, useState } from 'react';
import { AppLayout } from '../components/AppLayout';
import { getActionLogs, type ActionLogsResponse } from '../api/reports';
import { toLocalDateInputValue } from '../utils/date';

interface ApiErrorShape {
  response?: {
    status?: number;
    data?: {
      detail?: unknown;
    };
  };
  message?: string;
}

const formatAuditTimestamp = (value: string | null) => {
  if (!value) return '-';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  });
};

const toInputDate = (d: Date) => toLocalDateInputValue(d);

const getFrequencyDateWindow = (frequency: 'monthly' | 'quarterly' | 'annually', baseDate: Date) => {
  const year = baseDate.getFullYear();
  const month = baseDate.getMonth();
  if (frequency === 'monthly') {
    const start = new Date(year, month, 1);
    const end = new Date(baseDate);
    return { from: toInputDate(start), to: toInputDate(end) };
  }
  if (frequency === 'quarterly') {
    const start = new Date(baseDate);
    start.setMonth(start.getMonth() - 3);
    const end = new Date(baseDate);
    return { from: toInputDate(start), to: toInputDate(end) };
  }
  const start = new Date(year, 0, 1);
  const end = new Date(baseDate);
  return { from: toInputDate(start), to: toInputDate(end) };
};

const getErrorMessage = (reason: unknown): string => {
  const error = reason as ApiErrorShape;
  const status = error?.response?.status;
  const detail = error?.response?.data?.detail;

  let msg = '';
  if (typeof detail === 'string') {
    msg = detail;
  } else if (Array.isArray(detail)) {
    msg = detail
      .map((d) => {
        if (d && typeof d === 'object' && 'msg' in d && typeof (d as { msg?: string }).msg === 'string') {
          return (d as { msg: string }).msg;
        }
        return '';
      })
      .filter(Boolean)
      .join(', ');
  } else if (detail && typeof detail === 'object' && 'message' in detail && typeof (detail as { message?: string }).message === 'string') {
    msg = (detail as { message: string }).message;
  } else if (typeof error?.message === 'string') {
    msg = error.message;
  }

  if (status && msg) {
    return `${status}: ${msg}`;
  }
  if (status) {
    return `${status}`;
  }
  return msg || 'request failed';
};

const withTimeout = <T,>(promise: Promise<T>, timeoutMs = 15000, label = 'Request'): Promise<T> => {
  return new Promise<T>((resolve, reject) => {
    const timeoutId = window.setTimeout(() => {
      reject(new Error(`${label} timed out after ${timeoutMs}ms`));
    }, timeoutMs);

    promise
      .then((result) => {
        window.clearTimeout(timeoutId);
        resolve(result);
      })
      .catch((error) => {
        window.clearTimeout(timeoutId);
        reject(error);
      });
  });
};

const ActionLogsPage = () => {
  const today = new Date();
  const defaultWindow = getFrequencyDateWindow('monthly', today);
  const [dateRange, setDateRange] = useState<{ from: string; to: string }>({
    from: defaultWindow.from,
    to: defaultWindow.to,
  });
  const [loading, setLoading] = useState(false);
  const [fetchWarning, setFetchWarning] = useState('');
  const [dateInputError, setDateInputError] = useState('');

  // Action Logs State
  const [actionLogsData, setActionLogsData] = useState<ActionLogsResponse | null>(null);
  const [actionLogModule, setActionLogModule] = useState('all');
  const [actionLogType, setActionLogType] = useState('all');
  const [actionLogUserQuery, setActionLogUserQuery] = useState('');
  const [actionLogReference, setActionLogReference] = useState('');
  const [actionLogPage, setActionLogPage] = useState(1);
  const [actionLogPageSize, setActionLogPageSize] = useState(20);

  const fromDate = dateRange.from;
  const toDate = dateRange.to;
  const todayInput = toLocalDateInputValue(today);
  const fromDateMax = toDate && toDate < todayInput ? toDate : todayInput;

  const handleFromDateChange = (value: string) => {
    setActionLogPage(1);
    setDateRange((prev) => {
      const nextToDate = prev.to && value && value > prev.to ? value : prev.to;
      return { from: value, to: nextToDate };
    });
  };

  const handleToDateChange = (value: string) => {
    setActionLogPage(1);
    setDateRange((prev) => {
      const nextFromDate = prev.from && value && value < prev.from ? value : prev.from;
      return { from: nextFromDate, to: value };
    });
  };

  const handleActionLogPageSizeChange = (value: number) => {
    setActionLogPageSize(value);
    setActionLogPage(1);
  };

  // Fetch Action Logs
  useEffect(() => {
    const fetchActionLogs = async () => {
      if (!fromDate || !toDate) {
        return;
      }

      setLoading(true);
      setFetchWarning('');
      setDateInputError('');

      try {
        const actionLogsRes = await withTimeout(
          getActionLogs(
            fromDate,
            toDate,
            actionLogModule,
            actionLogType,
            actionLogUserQuery,
            actionLogReference,
            actionLogPage,
            actionLogPageSize
          ),
          20000,
          'Action Logs'
        );

        setActionLogsData(actionLogsRes || null);
      } catch (err) {
        const errorMsg = getErrorMessage(err);
        console.error('Failed to fetch action logs:', errorMsg);
        setFetchWarning(errorMsg);
        setActionLogsData(null);
      } finally {
        setLoading(false);
      }
    };

    fetchActionLogs();
    
    // Auto-refresh every 10 seconds for real-time updates
    const intervalId = setInterval(() => {
      fetchActionLogs();
    }, 10000);
    
    // Cleanup interval on unmount or when dependencies change
    return () => clearInterval(intervalId);
  }, [fromDate, toDate, actionLogModule, actionLogType, actionLogUserQuery, actionLogReference, actionLogPage, actionLogPageSize]);

  return (
    <AppLayout title="Action Logs">
      <div className="space-y-4">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-neutral-900">Action Logs</h1>
          <p className="mt-1 text-sm text-neutral-600">View and filter system action logs across all modules</p>
        </div>

        {/* Date Range and Frequency Controls */}
        <div className="hms-card">
          <div className="flex flex-col gap-4 p-4">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div>
                <label className="block text-xs font-semibold text-neutral-700">From Date</label>
                <input
                  type="date"
                  value={fromDate}
                  onChange={(e) => handleFromDateChange(e.target.value)}
                  max={fromDateMax}
                  disabled={loading}
                  className="mt-1 block w-full rounded border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-900 placeholder-neutral-500 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:bg-neutral-100"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-neutral-700">To Date</label>
                <input
                  type="date"
                  value={toDate}
                  onChange={(e) => handleToDateChange(e.target.value)}
                  max={todayInput}
                  disabled={loading}
                  className="mt-1 block w-full rounded border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-900 placeholder-neutral-500 focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:bg-neutral-100"
                />
              </div>
            </div>
            <p className="text-xs text-neutral-600">
              Action logs are filtered only by date range and filters below. Frequency selection is not applicable.
            </p>
            {dateInputError && <div className="text-xs text-red-600">{dateInputError}</div>}
            {fetchWarning && <div className="text-xs text-amber-600">{fetchWarning}</div>}
          </div>
        </div>

        {/* Loading State */}
        {loading && (
          <div className="hms-card px-5 py-4 text-center">
            <div className="inline-block animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
            <p className="mt-2 text-sm text-neutral-600">Loading action logs...</p>
          </div>
        )}

        {/* Action Logs Table */}
        {!loading && actionLogsData && (
          <div className="hms-card overflow-hidden">
            <div className="border-b border-neutral-200 bg-neutral-50 p-4">
              <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
                <h3 className="text-sm font-bold text-neutral-800">{actionLogsData.report_title}</h3>
                <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-5">
                  <select
                    value={actionLogModule}
                    onChange={(e) => {
                      setActionLogModule(e.target.value);
                      setActionLogPage(1);
                    }}
                    className="rounded border border-neutral-300 bg-white px-2 py-1 text-xs text-neutral-700"
                  >
                    <option value="all">All Modules</option>
                    <option value="invoices">Invoices</option>
                    <option value="quotations">Quotations</option>
                    <option value="purchase-orders">Purchase Orders</option>
                    <option value="grn">GRN</option>
                    <option value="payments">Payments</option>
                    <option value="stock">Stock</option>
                    <option value="sales-returns">Sales Returns</option>
                    <option value="purchase-returns">Purchase Returns</option>
                  </select>
                  <select
                    value={actionLogType}
                    onChange={(e) => {
                      setActionLogType(e.target.value);
                      setActionLogPage(1);
                    }}
                    className="rounded border border-neutral-300 bg-white px-2 py-1 text-xs text-neutral-700"
                  >
                    <option value="all">All Actions</option>
                    <option value="GET">GET</option>
                    <option value="POST">POST</option>
                    <option value="PUT">PUT</option>
                    <option value="PATCH">PATCH</option>
                    <option value="DELETE">DELETE</option>
                    <option value="LOGIN">LOGIN</option>
                    <option value="LOGOUT">LOGOUT</option>
                    <option value="VIEW_ACTION_LOGS">VIEW_ACTION_LOGS</option>
                  </select>
                  <input
                    type="text"
                    value={actionLogUserQuery}
                    onChange={(e) => {
                      setActionLogUserQuery(e.target.value);
                      setActionLogPage(1);
                    }}
                    placeholder="User / Email / ID"
                    className="rounded border border-neutral-300 bg-white px-2 py-1 text-xs text-neutral-700"
                  />
                  <input
                    type="text"
                    value={actionLogReference}
                    onChange={(e) => {
                      setActionLogReference(e.target.value);
                      setActionLogPage(1);
                    }}
                    placeholder="Reference"
                    className="rounded border border-neutral-300 bg-white px-2 py-1 text-xs text-neutral-700"
                  />
                  <select
                    value={actionLogPageSize}
                    onChange={(e) => handleActionLogPageSizeChange(Number(e.target.value))}
                    className="rounded border border-neutral-300 bg-white px-2 py-1 text-xs text-neutral-700"
                  >
                    <option value={10}>10 rows</option>
                    <option value={20}>20 rows</option>
                    <option value={50}>50 rows</option>
                  </select>
                </div>
              </div>
              <p className="mt-2 text-xs text-neutral-600">
                Period: {actionLogsData.from_date_display || fromDate} to {actionLogsData.to_date_display || toDate} | Total Events: {actionLogsData.total}
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-neutral-100 text-xs uppercase tracking-wide text-neutral-600">
                    <th className="px-3 py-2 text-left">Timestamp</th>
                    <th className="px-3 py-2 text-left">User</th>
                    <th className="px-3 py-2 text-left">Module</th>
                    <th className="px-3 py-2 text-left">Action Type</th>
                    <th className="px-3 py-2 text-left">Reference</th>
                    <th className="px-3 py-2 text-left">Description</th>
                    <th className="px-3 py-2 text-left">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {actionLogsData.items.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-6 text-center text-neutral-500">
                        No action logs found for selected filters.
                      </td>
                    </tr>
                  ) : (
                    actionLogsData.items.map((item) => (
                      <tr key={item.id} className="border-b border-neutral-100 align-top">
                        <td className="px-3 py-2 text-left">{formatAuditTimestamp(item.timestamp)}</td>
                        <td className="px-3 py-2 text-left">{item.user_name || item.user_id || 'System'}</td>
                        <td className="px-3 py-2 text-left">{item.module_name || '-'}</td>
                        <td className="px-3 py-2 text-left">{item.action_type || '-'}</td>
                        <td className="px-3 py-2 text-left">{(item.reference && item.reference.trim()) || (item.record_reference && item.record_reference.trim()) || '-'}</td>
                        <td className="px-3 py-2 text-left">{item.description || item.action || '-'}</td>
                        <td className="px-3 py-2 text-left">{item.status || '-'}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            {actionLogsData.total_pages > 1 && (
              <div className="flex items-center justify-between border-t border-neutral-200 bg-white px-4 py-3 text-xs text-neutral-600">
                <span>Page {actionLogsData.page} of {actionLogsData.total_pages}</span>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    disabled={actionLogsData.page <= 1}
                    onClick={() => setActionLogPage((prev) => Math.max(1, prev - 1))}
                    className="rounded border border-neutral-300 bg-white px-3 py-1 font-semibold text-neutral-700 hover:bg-neutral-100 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Previous
                  </button>
                  <button
                    type="button"
                    disabled={actionLogsData.page >= actionLogsData.total_pages}
                    onClick={() => setActionLogPage((prev) => prev + 1)}
                    className="rounded border border-neutral-300 bg-white px-3 py-1 font-semibold text-neutral-700 hover:bg-neutral-100 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* No data state */}
        {!loading && !actionLogsData && !fetchWarning && (
          <div className="hms-card px-5 py-4 text-center text-sm text-neutral-600">
            Select date range to load action logs
          </div>
        )}
      </div>
    </AppLayout>
  );
};

export default ActionLogsPage;
