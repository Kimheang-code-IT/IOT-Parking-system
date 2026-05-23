import { computed, ref, watch } from 'vue'
import type { SortingState, PaginationState, ColumnFiltersState } from '@tanstack/vue-table'

export interface TableQueryOptions {
  initialSorting?: SortingState
  initialPageSize?: number
  initialGlobalFilter?: string
  extraFilters?: Record<string, unknown>
}

export function useTableQuery(options: TableQueryOptions = {}) {
  // SSR-safe query states for backend API interactions.
  // We avoid storing DOM-specific state or localStorage here.
  const sorting = ref<SortingState>(options.initialSorting || [])
  const globalFilter = ref(options.initialGlobalFilter || '')
  const columnFilters = ref<ColumnFiltersState>([])
  
  const pagination = ref<PaginationState>({
    pageIndex: 0,
    pageSize: options.initialPageSize || 15
  })

  // Computed properties for API consumption could go here
  // e.g. serverSort = computed(() => sorting.value.map(s => `${s.id}:${s.desc ? 'desc' : 'asc'}`).join(','))

  function resetQueryState() {
    globalFilter.value = ''
    columnFilters.value = []
    pagination.value.pageIndex = 0
    if (options.initialSorting) {
      sorting.value = [...options.initialSorting]
    }
  }

  const serverQuery = computed(() => {
    const sort = sorting.value[0]
    return {
      page: pagination.value.pageIndex + 1,
      limit: pagination.value.pageSize,
      sortBy: sort?.id || undefined,
      sortOrder: sort ? (sort.desc ? 'desc' as const : 'asc' as const) : undefined,
      search: globalFilter.value || undefined,
      ...(options.extraFilters || {})
    }
  })

  watch([globalFilter, sorting, columnFilters], () => {
    pagination.value.pageIndex = 0
  })

  return {
    sorting,
    globalFilter,
    columnFilters,
    pagination,
    serverQuery,
    resetQueryState
  }
}
