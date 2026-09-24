import { useEffect, useRef, useState } from 'react';
import type { PaginatedResourceActions, PaginatedResourceState } from '../../hooks/usePaginatedResource';

export interface Column<T> {
  key: string;
  header: string;
  sortable?: boolean;
  render?: (item: T) => React.ReactNode;
  className?: string;
}

export interface FilterOption {
  key: string;
  label: string;
  options: { value: string; label: string }[];
}

export interface DataTableProps<T> {
  resource: PaginatedResourceState<T> & PaginatedResourceActions;
  columns: Column<T>[];
  searchPlaceholder?: string;
  showSearch?: boolean;
  showFilters?: boolean;
  showPagination?: boolean;
  filterOptions?: FilterOption[];
  emptyMessage?: string;
  onRowClick?: (item: T) => void;
  toolbar?: React.ReactNode;
}

const pageSizes = [5, 10, 15, 25, 50];

/**
 * The single reusable data table for all list pages.
 * It is driven by the usePaginatedResource hook and renders search,
 * filters, sortable columns, pagination, loading and empty states.
 */
export const DataTable = <T,>({
  resource,
  columns,
  searchPlaceholder = 'Search...',
  showSearch = true,
  showFilters = false,
  showPagination = true,
  filterOptions = [],
  emptyMessage = 'No data available',
  onRowClick,
  toolbar,
}: DataTableProps<T>) => {
  const [searchInput, setSearchInput] = useState(resource.search);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setSearchInput(resource.search);
  }, [resource.search]);

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setSearchInput(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      resource.setSearch(value);
    }, 400);
  };

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const handleSort = (column: Column<T>) => {
    if (!column.sortable) return;
    if (resource.sortBy === column.key) {
      resource.setSort(column.key, resource.sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      resource.setSort(column.key, 'asc');
    }
  };

  const getSortIndicator = (key: string) => {
    if (resource.sortBy !== key) return null;
    return resource.sortOrder === 'asc' ? '↑' : '↓';
  };

  const totalPages = Math.max(1, Math.ceil(resource.total / resource.pageSize));

  return (
    <div className="bg-white rounded-lg border border-mistral-border overflow-hidden">
      {(showSearch || showFilters || toolbar) && (
        <div className="p-4 border-b border-mistral-border flex flex-wrap gap-4 items-center bg-white">
          {showSearch && (
            <div className="flex-1 min-w-64">
              <input
                type="text"
                placeholder={searchPlaceholder}
                value={searchInput}
                onChange={handleSearchChange}
                className="w-full px-4 py-2 text-sm bg-white border border-mistral-border-strong rounded-md placeholder:text-mistral-muted/70 text-mistral-ink focus:outline-none focus:border-mistral-ink transition-colors duration-200"
              />
            </div>
          )}
          {showFilters && filterOptions.length > 0 && (
            <div className="flex gap-3 flex-wrap">
              {filterOptions.map((filter) => (
                <select
                  key={filter.key}
                  value={resource.filters[filter.key] || ''}
                  onChange={(e) => resource.setFilter(filter.key, e.target.value)}
                  className="px-3 py-2 font-mono text-xs uppercase tracking-wide bg-white border border-mistral-border-strong rounded-md text-mistral-muted focus:outline-none focus:border-mistral-ink transition-colors duration-200"
                >
                  <option value="">All {filter.label}</option>
                  {filter.options.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              ))}
            </div>
          )}
          {toolbar}
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-mistral-band">
            <tr>
              {columns.map((column) => (
                <th
                  key={column.key}
                  className={`px-6 py-3 text-left font-mono text-[11px] font-normal uppercase tracking-widest text-mistral-muted border-b border-mistral-border ${column.className || ''}`}
                  onClick={() => handleSort(column)}
                  style={column.sortable ? { cursor: 'pointer' } : undefined}
                >
                  {column.header}
                  {column.sortable && (
                    <span className="ml-1 text-mistral-muted/80">{getSortIndicator(column.key)}</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-white">
            {resource.isLoading ? (
              <tr>
                <td colSpan={columns.length} className="px-6 py-12 text-center">
                  <div className="flex items-center justify-center gap-3 text-mistral-muted font-mono text-xs uppercase tracking-wide">
                    <svg className="animate-spin h-4 w-4 text-mistral-ink" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Loading...
                  </div>
                </td>
              </tr>
            ) : resource.items.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-6 py-12 text-center text-sm text-mistral-muted">
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              resource.items.map((item, index) => (
                <tr
                  key={(item as { id?: string | number }).id ?? index}
                  className={`border-b border-mistral-border last:border-b-0 hover:bg-mistral-surface transition-colors duration-200 ${onRowClick ? 'cursor-pointer' : ''}`}
                  onClick={onRowClick ? () => onRowClick(item) : undefined}
                >
                  {columns.map((column) => (
                    <td
                      key={column.key}
                      className={`px-6 py-4 text-sm text-mistral-ink ${column.className || ''}`}
                    >
                      {column.render
                        ? column.render(item)
                        : ((item as Record<string, unknown>)[column.key] as React.ReactNode) ?? '-'}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {showPagination && resource.total > 0 && (
        <div className="p-4 border-t border-mistral-border flex flex-wrap items-center justify-between gap-4 bg-white">
          <div className="font-mono text-xs text-mistral-muted uppercase tracking-wide">
            Showing {resource.page * resource.pageSize - resource.pageSize + 1} to{' '}
            {Math.min(resource.page * resource.pageSize, resource.total)} of {resource.total}
          </div>
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 font-mono text-xs text-mistral-muted uppercase tracking-wide">
              Rows
              <select
                value={resource.pageSize}
                onChange={(e) => resource.setPageSize(Number(e.target.value))}
                className="px-2 py-1 bg-white border border-mistral-border-strong rounded-md text-mistral-ink focus:outline-none focus:border-mistral-ink transition-colors duration-200"
              >
                {pageSizes.map((size) => (
                  <option key={size} value={size}>
                    {size}
                  </option>
                ))}
              </select>
            </label>
            <div className="flex gap-2 items-center">
              <button
                className="px-3 py-1.5 font-display text-sm border border-mistral-border-strong rounded-md text-mistral-ink hover:border-mistral-ink transition-colors duration-200 disabled:opacity-40 disabled:hover:border-mistral-border-strong"
                disabled={resource.page === 1}
                onClick={() => resource.setPage(resource.page - 1)}
              >
                Previous
              </button>
              <span className="px-1 font-mono text-xs text-mistral-muted">
                {resource.page} / {totalPages}
              </span>
              <button
                className="px-3 py-1.5 font-display text-sm border border-mistral-border-strong rounded-md text-mistral-ink hover:border-mistral-ink transition-colors duration-200 disabled:opacity-40 disabled:hover:border-mistral-border-strong"
                disabled={resource.page >= totalPages}
                onClick={() => resource.setPage(resource.page + 1)}
              >
                Next
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// Shared badge components used by multiple tables

const badgeBase =
  'inline-flex items-center px-2 py-0.5 rounded-sm border font-mono text-[11px] uppercase tracking-wide whitespace-nowrap';

export const StatusBadge: React.FC<{ status: string; className?: string }> = ({ status, className = '' }) => {
  const statusClasses: Record<string, string> = {
    pending: 'bg-mistral-yellow-tint border-mistral-yellow/70 text-mistral-ink',
    processing: 'bg-mistral-blue-tint border-mistral-blue/40 text-mistral-ink',
    completed: 'bg-mistral-green-tint border-mistral-green/50 text-mistral-ink',
    failed: 'bg-mistral-red-tint border-mistral-red/60 text-mistral-ink',
    waiting: 'bg-mistral-band border-mistral-border-strong text-mistral-muted',
  };
  return (
    <span className={`${badgeBase} ${statusClasses[status] || 'bg-mistral-band border-mistral-border-strong text-mistral-muted'} ${className}`}>
      {status}
    </span>
  );
};

export const SeverityBadge: React.FC<{ severity: string; className?: string }> = ({ severity, className = '' }) => {
  const severityClasses: Record<string, string> = {
    low: 'bg-mistral-green-tint border-mistral-green/50 text-mistral-ink',
    medium: 'bg-mistral-yellow-tint border-mistral-yellow/70 text-mistral-ink',
    high: 'bg-mistral-orange-tint border-mistral-orange/50 text-mistral-ink',
    critical: 'bg-mistral-red-tint border-mistral-red/60 text-mistral-ink',
  };
  return (
    <span className={`${badgeBase} ${severityClasses[severity] || 'bg-mistral-band border-mistral-border-strong text-mistral-muted'} ${className}`}>
      {severity}
    </span>
  );
};

export const BackendBadge: React.FC<{ backend: string; className?: string }> = ({ backend, className = '' }) => {
  const backendClasses: Record<string, string> = {
    typesafe: 'bg-mistral-pink-tint border-mistral-pink/60 text-mistral-ink',
    mistral: 'bg-mistral-blue-tint border-mistral-blue/40 text-mistral-ink',
    combined: 'bg-mistral-orange-tint border-mistral-orange/50 text-mistral-ink',
  };
  return (
    <span className={`${badgeBase} ${backendClasses[backend] || 'bg-mistral-band border-mistral-border-strong text-mistral-muted'} ${className}`}>
      {backend}
    </span>
  );
};

export const CategoryBadge: React.FC<{ category: string | null; className?: string }> = ({ category, className = '' }) => {
  const categoryClasses: Record<string, string> = {
    hate: 'bg-mistral-red-tint border-mistral-red/60 text-mistral-ink',
    harassment: 'bg-mistral-orange-tint border-mistral-orange/50 text-mistral-ink',
    violence: 'bg-mistral-red-tint border-mistral-red-deep/40 text-mistral-ink',
    self_harm: 'bg-mistral-pink-tint border-mistral-pink/60 text-mistral-ink',
    sexual: 'bg-mistral-pink-tint border-mistral-pink/40 text-mistral-ink',
    spam: 'bg-mistral-band border-mistral-border-strong text-mistral-muted',
    illegal: 'bg-mistral-ink border-transparent text-mistral-surface',
    safe: 'bg-mistral-green-tint border-mistral-green/50 text-mistral-ink',
  };
  return (
    <span className={`${badgeBase} ${categoryClasses[category || ''] || 'bg-mistral-band border-mistral-border-strong text-mistral-muted'} ${className}`}>
      {category || 'none'}
    </span>
  );
};

export const PlatformBadge: React.FC<{ platform: string | null; className?: string }> = ({ platform, className = '' }) => {
  if (!platform) return <span className="text-mistral-muted/60">-</span>;
  return (
    <span className={`${badgeBase} bg-mistral-band border-mistral-border-strong text-mistral-muted ${className}`}>
      {platform}
    </span>
  );
};
