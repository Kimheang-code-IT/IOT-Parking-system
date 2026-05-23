<script setup lang="ts">
type PaginationState = {
  pageIndex: number
  pageSize: number
}
type PageSizeOption = number | 'All'
const PAGE_SIZE_OPTIONS: PageSizeOption[] = [10, 20, 50, 100, 200, 1000, 'All']
const pagination = defineModel<PaginationState>('pagination', {
  default: () => ({ pageIndex: 0, pageSize: 15 })
})

const props = defineProps<{
  total: number
  selectedCount?: number
  allSelected?: boolean
  selectable?: boolean
}>()

defineEmits<{
  (e: 'toggle-select-all', val: boolean): void
}>()

function handlePageSizeChange(val: PageSizeOption) {
  const pageSize = val === 'All' ? props.total : Number(val)
  pagination.value = {
    ...pagination.value,
    pageSize: pageSize > 0 ? pageSize : 1,
    pageIndex: 0
  }
}

function handlePageChange(page: number) {
  pagination.value = {
    ...pagination.value,
    pageIndex: Math.max(0, page - 1)
  }
}
</script>

<template>
  <div class="flex flex-row items-center justify-between border-t border-accented py-2 px-3 gap-2 shrink-0 bg-background/50 w-full overflow-hidden">
    <!-- Rows per page selector (Left) -->
    <div class="flex items-center gap-1 shrink-0">
      <span class="text-[10px] text-muted-foreground whitespace-nowrap hidden sm:inline">{{ 'Rows per page' }}</span>
      <USelect
        :model-value="pagination.pageSize"
        @update:model-value="(val) => handlePageSizeChange(val as PageSizeOption)"
        :items="PAGE_SIZE_OPTIONS"
        variant="ghost"
        size="xs"
        class="font-normal text-foreground w-20"
      />
    </div>

    <!-- Page Controls (Right) -->
    <div class="flex items-center gap-4">

      <UPagination
        :page="(pagination.pageIndex || 0) + 1"
        :items-per-page="pagination.pageSize"
        :total="total"
        @update:page="handlePageChange"
        active-color="primary"
        size="xs"
        class="shrink-0"
      />
    </div>
  </div>
</template>
