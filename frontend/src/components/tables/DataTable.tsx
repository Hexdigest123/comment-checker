import { useState, useMemo, useCallback } from 'react';
import type { PageParams, Comment, Classification } from '../../types';
import { Button } from '../ui';

interface Column<T> {
  key: string;
  header: string;
  sortable?: boolean;
  render?: (item: T) => React.ReactNode;
  className?: string;
}

interface DataTableProps<T> {
  data: T[];
  columns: Column<T>[];
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
  onSortChange?: (sortBy: string, sortOrder: 'asc' | 'desc') => void;
  onSearchChange?: (search: string) => void;
  onFilterChange?: (filters: Record<string, string>) => void;
  currentSortBy?: string;
  currentSortOrder?: 'asc' | 'desc';
  currentSearch?: string;
  currentFilters?: Record<string, string>;
  searchPlaceholder?: string;
  showSearch?: boolean;
  showPagination?: boolean;
  showFilters?: boolean;
  filterOptions?: { key: string; label: string; options: { value: string; label: string }[] }[];
  isLoading?: boolean;
  emptyMessage?: string;
}

export const DataTable = <T,>({
  data,
  columns,
  total,
  page,
  pageSize,
  onPageChange,
  onPageSizeChange,
  onSortChange,
  onSearchChange,
  onFilterChange,
  currentSortBy,
  currentSortOrder = 'asc',
  currentSearch = '',
  currentFilters = {},
  searchPlaceholder = 'Search...',
  showSearch = true,
  showPagination = true,
  showFilters = false,
  filterOptions = [],
  isLoading = false,
  emptyMessage = 'No data available',
}: DataTableProps<T>) => {
  const [searchValue, setSearchValue] = useState(currentSearch);
  const [filterValues, setFilterValues] = useState<Record<string, string>>(currentFilters);

  const pageSizes = [5, 10, 15, 25];

  const handleSort = useCallback((key: string) => {
    if (!onSortChange) return;

    let newSortOrder: 'asc' | 'desc' = 'asc';
    if (currentSortBy === key) {
      newSortOrder = currentSortOrder === 'asc' ? 'desc' : 'asc';
    }

    onSortChange(key, newSortOrder);
  }, [currentSortBy, currentSortOrder, onSortChange]);

  const handleSearch = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setSearchValue(value);
    if (onSearchChange) {
      // Debounce search
      const timer = setTimeout(() => {
        onSearchChange(value);
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [onSearchChange]);

  const handleFilterChange = useCallback((key: string, value: string) => {
    const newFilters = { ...filterValues, [key]: value };
    setFilterValues(newFilters);
    if (onFilterChange) {
      onFilterChange(newFilters);
    }
  }, [filterValues, onFilterChange]);

  const getSortIndicator = (key: string) => {
    if (currentSortBy !== key) return null;
    return currentSortOrder === 'asc' ? '↑' : '↓';
  };

  const totalPages = useMemo(() => Math.ceil(total / pageSize), [total, pageSize]);

  return (
    <div className="bg-white rounded-lg shadow-sm border">
      {/* Search and Filters */}
      {(showSearch || showFilters) && (
        <div className="p-4 border-b flex flex-wrap gap-4 items-center">
          {showSearch && (
            <div className="flex-1 min-w-64">
              <input
                type="text"
                placeholder={searchPlaceholder}
                value={searchValue}
                onChange={handleSearch}
                className="w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          )}
          {showFilters && filterOptions.length > 0 && (
            <div className="flex gap-4 flex-wrap">
              {filterOptions.map((filter) => (
                <select
                  key={filter.key}
                  value={filterValues[filter.key] || ''}
                  onChange={(e) => handleFilterChange(filter.key, e.target.value)}
                  className="px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">{filter.label}</option>
                  {filter.options.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              {columns.map((column) => (
                <th
                  key={column.key}
                  className={`px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider ${column.className || ''}`}
                  onClick={() => column.sortable && handleSort(column.key)}
                  style={column.sortable ? { cursor: 'pointer' } : {}}
                >
                  <div className="flex items-center">
                    {column.header}
                    {column.sortable && (
                      <span className="ml-1">{getSortIndicator(column.key)}</span>
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {isLoading ? (
              <tr>
                <td colSpan={columns.length} className="px-6 py-4 text-center">
                  <div className="flex items-center justify-center">
                    <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Loading...
                  </div>
                </td>
              </tr>
            ) : data.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-6 py-4 text-center text-gray-500">
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              data.map((item, index) => (
                <tr key={(item as { id?: string }).id || index} className="hover:bg-gray-50">
                  {columns.map((column) => (
                    <td
                      key={column.key}
                      className={`px-6 py-4 whitespace-nowrap text-sm text-gray-900 ${column.className || ''}`}
                    >
                      {column.render ? column.render(item) : (item as Record<string, unknown>)[column.key] as React.ReactNode}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {showPagination && total > 0 && (
        <div className="p-4 border-t flex flex-wrap items-center justify-between gap-4">
          <div className="text-sm text-gray-500">
            Showing {page * pageSize - pageSize + 1} to {Math.min(page * pageSize, total)} of {total}
          </div>
          <div className="flex items-center gap-4">
            <div className="flex gap-2">
              {pageSizes.map((size) => (
                <Button
                  key={size}
                  variant={pageSize === size ? 'primary' : 'outline'}
                  size="sm"
                  onClick={() => onPageSizeChange(size)}
                >
                  {size}
                </Button>
              ))}
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page === 1}
                onClick={() => onPageChange(page - 1)}
              >
                Previous
              </Button>
              <span className="px-4 py-2 text-sm">
                Page {page} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page === totalPages}
                onClick={() => onPageChange(page + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// Status badge component for tables
export const StatusBadge: React.FC<{ status: string; className?: string }> = ({ status, className = '' }) => {
  const statusClasses = {
    pending: 'bg-yellow-100 text-yellow-800',
    processing: 'bg-blue-100 text-blue-800',
    completed: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
    waiting: 'bg-gray-100 text-gray-800',
  };

  return (
    <span
      className={`px-2 py-1 rounded-full text-xs font-medium ${statusClasses[status as keyof typeof statusClasses] || 'bg-gray-100 text-gray-800'} ${className}`}
    >
      {status}
    </span>
  );
};

// Severity badge component
export const SeverityBadge: React.FC<{ severity: string; className?: string }> = ({ severity, className = '' }) => {
  const severityClasses = {
    low: 'bg-green-100 text-green-800',
    medium: 'bg-yellow-100 text-yellow-800',
    high: 'bg-orange-100 text-orange-800',
    critical: 'bg-red-100 text-red-800',
  };

  return (
    <span
      className={`px-2 py-1 rounded-full text-xs font-medium ${severityClasses[severity as keyof typeof severityClasses] || 'bg-gray-100 text-gray-800'} ${className}`}
    >
      {severity}
    </span>
  );
};

// Backend badge component
export const BackendBadge: React.FC<{ backend: string; className?: string }> = ({ backend, className = '' }) => {
  const backendClasses = {
    typesafe: 'bg-purple-100 text-purple-800',
    mistral: 'bg-indigo-100 text-indigo-800',
    combined: 'bg-cyan-100 text-cyan-800',
  };

  return (
    <span
      className={`px-2 py-1 rounded-full text-xs font-medium ${backendClasses[backend as keyof typeof backendClasses] || 'bg-gray-100 text-gray-800'} ${className}`}
    >
      {backend}
    </span>
  );
};

// Category badge component
export const CategoryBadge: React.FC<{ category: string; className?: string }> = ({ category, className = '' }) => {
  const categoryClasses = {
    hate: 'bg-red-100 text-red-800',
    harassment: 'bg-orange-100 text-orange-800',
    violence: 'bg-red-100 text-red-800',
    self_harm: 'bg-purple-100 text-purple-800',
    sexual: 'bg-pink-100 text-pink-800',
    spam: 'bg-gray-100 text-gray-800',
    illegal: 'bg-black text-white',
    safe: 'bg-green-100 text-green-800',
  };

  return (
    <span
      className={`px-2 py-1 rounded-full text-xs font-medium ${categoryClasses[category as keyof typeof categoryClasses] || 'bg-gray-100 text-gray-800'} ${className}`}
    >
      {category}
    </span>
  );
};

// Comment-specific columns for reuse
export const commentColumns: Column<Comment>[] = [
  { key: 'text', header: 'Comment', sortable: true, className: 'max-w-md' },
  { key: 'source_url', header: 'Source URL', sortable: true, className: 'max-w-xs' },
  { key: 'status', header: 'Status', sortable: true, render: (item) => <StatusBadge status={item.status} /> },
  { key: 'created_at', header: 'Created At', sortable: true },
];

// Classification-specific columns
export const classificationColumns: Column<Classification>[] = [
  { key: 'comment_id', header: 'Comment ID', sortable: true },
  { key: 'backend', header: 'Backend', sortable: true, render: (item) => <BackendBadge backend={item.backend} /> },
  { key: 'category', header: 'Category', sortable: true, render: (item) => <CategoryBadge category={item.category} /> },
  { key: 'severity', header: 'Severity', sortable: true, render: (item) => <SeverityBadge severity={item.severity} /> },
  { key: 'confidence', header: 'Confidence', sortable: true, render: (item) => `${(item.confidence * 100).toFixed(1)}%` },
  { key: 'harmful_score', header: 'Harmful Score', sortable: true, render: (item) => item.harmful_score.toFixed(2) },
  { key: 'created_at', header: 'Classified At', sortable: true },
];
