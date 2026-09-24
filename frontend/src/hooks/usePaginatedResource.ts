import { useCallback, useEffect, useRef, useState } from 'react';
import type { PageResponse } from '../types';

export type SortOrder = 'asc' | 'desc';

export interface PaginatedResourceState<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  search: string;
  sortBy: string;
  sortOrder: SortOrder;
  filters: Record<string, string>;
  isLoading: boolean;
  error: string;
}

export interface PaginatedResourceActions {
  setPage: (page: number) => void;
  setPageSize: (size: number) => void;
  setSearch: (search: string) => void;
  setSort: (sortBy: string, sortOrder: SortOrder) => void;
  setFilter: (key: string, value: string) => void;
  refetch: () => void;
}

/**
 * Reusable hook that drives any paginated, searchable, sortable backend
 * list endpoint. Pages only provide a fetcher; pagination/search/sort/filter
 * state and refetching are handled once here.
 */
export function usePaginatedResource<T>(
  fetcher: (params: Record<string, string | number>) => Promise<PageResponse<T>>,
  options?: {
    enabled?: boolean;
    initialPageSize?: number;
    initialSortBy?: string;
    initialSortOrder?: SortOrder;
    pollIntervalMs?: number;
  }
): PaginatedResourceState<T> & PaginatedResourceActions {
  const {
    enabled = true,
    initialPageSize = 10,
    initialSortBy = 'created_at',
    initialSortOrder = 'desc',
    pollIntervalMs = 0,
  } = options ?? {};

  const [items, setItems] = useState<T[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(initialPageSize);
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState(initialSortBy);
  const [sortOrder, setSortOrder] = useState<SortOrder>(initialSortOrder);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [tick, setTick] = useState(0);

  // Once the first fetch has completed, later fetches (polling ticks,
  // refetch() after votes, page/sort/filter changes) update silently so
  // the table does not flash a loading state on every refresh.
  const hasLoadedRef = useRef(false);

  const searchRef = useRef(search);
  searchRef.current = search;

  const fetchAll = useCallback(async () => {
    if (!enabled) return;
    if (!hasLoadedRef.current) setIsLoading(true);
    setError('');
    try {
      const params: Record<string, string | number> = {
        page,
        page_size: pageSize,
        sort_by: sortBy,
        sort_order: sortOrder,
      };
      const currentSearch = searchRef.current;
      if (currentSearch) params.search = currentSearch;
      for (const [key, value] of Object.entries(filters)) {
        if (value) params[key] = value;
      }
      const data = await fetcher(params);
      setItems(data.items);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch data');
    } finally {
      hasLoadedRef.current = true;
      setIsLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, page, pageSize, sortBy, sortOrder, filters, tick]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  // Optional polling (used to watch queue processing status)
  useEffect(() => {
    if (!pollIntervalMs || !enabled) return;
    const interval = setInterval(() => setTick((t) => t + 1), pollIntervalMs);
    return () => clearInterval(interval);
  }, [pollIntervalMs, enabled]);

  const setFilter = useCallback((key: string, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  }, []);

  const setPageSizeAndReset = useCallback((size: number) => {
    setPageSize(size);
    setPage(1);
  }, []);

  const setSearchDebounced = useCallback((value: string) => {
    setSearch(value);
    setPage(1);
  }, []);

  const setSort = useCallback((nextSortBy: string, nextSortOrder: SortOrder) => {
    setSortBy(nextSortBy);
    setSortOrder(nextSortOrder);
  }, []);

  const refetch = useCallback(() => setTick((t) => t + 1), []);

  return {
    items,
    total,
    page,
    pageSize,
    search,
    sortBy,
    sortOrder,
    filters,
    isLoading,
    error,
    setPage,
    setPageSize: setPageSizeAndReset,
    setSearch: setSearchDebounced,
    setSort,
    setFilter,
    refetch,
  };
}
