<template>
  <div class="flex flex-col w-full h-full min-h-0 flex-1 overflow-hidden border border-default rounded-xs bg-background shadow-sm">
    <!-- Header Toolbar -->
    <div
      v-if="title || $slots.header || globalFilter !== undefined || props.filterItems || props.filterItemsSecondary"
      class="flex flex-row items-center gap-2 px-3 py-2.5 border-b border-accented shrink-0 flex-wrap"
    >
      <div class="flex-1 flex items-center gap-2 min-w-0">
        <ClientOnly>
          <div v-if="title" class="min-w-0 hidden md:block">
            <h2 v-if="title" class="font-medium text-foreground tracking-tight leading-none truncate">{{ title }}
            </h2>
          </div>
        </ClientOnly>

        <!-- Custom Header Content Slot -->
        <slot name="header" />
      </div>

      <div class="flex flex-wrap items-center gap-2 shrink-0">
        <!-- Multi-Select Filters -->
        <CommonAppMutilSelect
          v-if="props.filterItems && props.filterItems.length"
          v-model="filterValue"
          :items="props.filterItems"
          :placeholder="props.filterPlaceholder || 'Filter'"
        />
        <CommonAppMutilSelect
          v-if="props.filterItemsSecondary && props.filterItemsSecondary.length"
          v-model="filterValueSecondary"
          :items="props.filterItemsSecondary"
          :placeholder="props.filterPlaceholderSecondary || 'Filter'"
        />
        <CommonAppMutilSelect
          v-if="props.filterItemsThird && props.filterItemsThird.length"
          v-model="filterValueThird"
          :items="props.filterItemsThird"
          :placeholder="props.filterPlaceholderThird || 'Filter'"
        />

        <!-- Global Filter Input -->
        <div v-if="globalFilter !== undefined" class="w-52">
          <CommonAppSearch v-model="globalFilter" />
        </div>
      </div>
    </div>

    <!-- Scrollable row area only (toolbar + pagination stay fixed) -->
    <div class="flex-1 min-h-0 h-0 overflow-hidden relative">
    <UTable ref="table" v-bind="$attrs" v-model:sorting="sorting" v-model:column-filters="columnFilters"
      v-model:global-filter="globalFilter" v-model:row-selection="rowSelection"
      v-model:column-visibility="columnVisibility" v-model:grouping="grouping" v-model:column-pinning="columnPinning"
      v-model:pagination="pagination" :pagination-options="{ getPaginationRowModel: getPaginationRowModel() }"
      :data="data" :columns="processedColumns" :loading="loading" :loading-options="{
        color: 'primary',
        animation: 'carousel'
      }" 
      :virtualize="virtualize ? { estimateSize: 44, overscan: 10 } : false"
      :sticky="($attrs.sticky as any) ?? 'header'"
      class="h-full min-h-0 scroll-shadow-right"
      :ui="{
        root: 'relative h-full min-h-0 overflow-auto',
        thead: 'sticky top-0 inset-x-0 z-10 bg-neutral-100 dark:bg-slate-800',
        th: 'py-2 px-3 text-sm font-normal text-muted-foreground bg-neutral-100 dark:bg-slate-800 whitespace-nowrap',
        tfoot: 'sticky bottom-0 inset-x-0 z-10 bg-muted/70 backdrop-blur-sm',
        tr: 'border-b border-accented/50 last:border-b-0',
        td: 'py-2 px-3 text-sm font-normal',
        ...(($attrs.ui as object) || {})
      }">
      <!-- Loading State: Skeleton Rows -->
      <template #loading-state>
        <div class="flex flex-col">
          <div v-for="i in 8" :key="i"
            class="flex items-center gap-4 px-4 py-4 border-b border-accented/50 last:border-0">
            <USkeleton class="h-4 w-8 shrink-0" />
            <USkeleton class="h-4 w-24 shrink-0" />
            <USkeleton class="h-4 flex-1" />
            <USkeleton class="h-4 w-32 shrink-0 hidden sm:block" />
            <USkeleton class="size-6 rounded-md shrink-0" />
          </div>
        </div>
      </template>

      <!-- Action Cell Implementation -->
      <template #action-cell="{ row }">
        <slot name="action-cell" :row="row">
          <UDropdownMenu v-if="getRowActions" :items="getRowActions(row.original)" :content="{ align: 'end' }">
            <UButton icon="i-lucide-ellipsis-vertical" color="neutral" variant="ghost" class="rounded-md" size="sm" />
          </UDropdownMenu>
        </slot>
      </template>

      <!-- Forward other slots -->
      <template v-for="(_, slotName) in $slots" #[slotName]="slotProps">
        <slot v-if="!['action-cell', 'header', 'footer'].includes(slotName as string)" :name="slotName"
          v-bind="slotProps" />
      </template>

      <!-- Empty State -->
      <template #empty>
        <slot name="empty">
          <div
            class="flex flex-col items-center justify-center flex-1 h-full w-full py-28 text-muted-foreground opacity-60">
            <UIcon name="i-lucide-database" class="size-20 mb-3" />
            <p class="text-xl font-normal italic">{{ $t('common.noData') }}</p>
          </div>
        </slot>
      </template>
    </UTable>
    </div>

    <!-- Unified Footer Pagination -->
    <div class="shrink-0 border-t border-accented">
    <ClientOnly>
      <CommonAppFooterPagin v-if="pagination" v-model:pagination="pagination"
        :total="props.totalRows ?? data.length"
        :selectable="selectable"
        :selected-count="Object.keys(rowSelection || {}).length"
        :all-selected="table?.table?.getIsAllRowsSelected() || false"
        @toggle-select-all="(val) => table?.table?.toggleAllRowsSelected(val)"
      />
    </ClientOnly>
    </div>
  </div>
</template>

<script setup lang="ts" generic="T">
import { h, computed, onMounted, useTemplateRef, resolveComponent } from 'vue'
import { useInfiniteScroll } from '@vueuse/core'
import type { TableColumn, DropdownMenuItem } from '@nuxt/ui'
import { getPaginationRowModel } from '@tanstack/vue-table'
import type { Column } from '@tanstack/vue-table'
import AppHeaderCell from './AppHeaderCell.vue'
import CommonAppMutilSelect from '~/components/common/AppMutilSelect.vue'
import CommonAppSearch from '~/components/common/AppSearch.vue'
import CommonAppFooterPagin from '~/components/common/AppFooterPagin.vue'


// Forward other slots
const props = withDefaults(defineProps<{
  data: T[]
  columns: TableColumn<T>[]
  loading?: boolean
  canLoadMore?: boolean
  virtualize?: boolean
  // getRowActions should return a flat array for NavigationMenu or Nested for Dropdown
  // In Nuxt UI v4, DropdownMenu items are DropdownMenuItem[][]
  getRowActions?: (item: T) => DropdownMenuItem[][]
  filterItems?: any[]
  filterPlaceholder?: string
  filterItemsSecondary?: any[]
  filterPlaceholderSecondary?: string
  filterItemsThird?: any[]
  filterPlaceholderThird?: string
  title?: string
  selectable?: boolean
  totalRows?: number
}>(), {
  canLoadMore: true,
  virtualize: true,
  selectable: true // Default to true if rowSelection is provided 
})

// V-Models for TanStack Table state
const filterValue = defineModel<any[]>('filterValue', { default: () => [] })
const filterValueSecondary = defineModel<any[]>('filterValueSecondary', { default: () => [] })
const filterValueThird = defineModel<any[]>('filterValueThird', { default: () => [] })
const sorting = defineModel<any>('sorting')
const columnFilters = defineModel<any>('columnFilters')
const globalFilter = defineModel<string>('globalFilter')
const rowSelection = defineModel<any>('rowSelection')
const columnVisibility = defineModel<any>('columnVisibility')
const grouping = defineModel<any>('grouping')
const columnPinning = defineModel<any>('columnPinning')
const pagination = defineModel<any>('pagination', {
  default: () => ({ pageIndex: 0, pageSize: 15 })
})

const emit = defineEmits<{
  (e: 'load-more'): void
}>()

const table = useTemplateRef<any>('table')

/**
 * Recursive logic to allow merged headers and apply Cell Registry.
 */
function processColumnDefinitions(cols: any[]): any[] {
  return cols.map(col => {
    if (col.columns && Array.isArray(col.columns)) {
      return {
        ...col,
        columns: processColumnDefinitions(col.columns)
      }
    }
    
    // Process new column definition
    const processed = { ...col }
    


    // Wrap sortable string headers with reusable AppHeaderCell (supports multi-sort logic)
    if (typeof processed.header === 'string' && processed.id !== 'action' && processed.accessorKey !== 'action' && processed.enableSorting !== false) {
      const label = processed.header
      const icon = processed.icon
      processed.header = ({ column }: { column: Column<T, any> }) => h(AppHeaderCell as any, { 
        column, 
        label, 
        icon: icon as string | undefined,
        multiSortCount: sorting.value?.length || 0
      })
    }
    
    // Action column — render label as plain styled text (no sorting)
    if (typeof processed.header === 'string' && (processed.id === 'action' || processed.accessorKey === 'action')) {
      const label = processed.header
      const icon = processed.icon
      processed.header = () => h('div', { class: 'flex items-center gap-1 px-[3px]' }, [
        icon ? h(resolveComponent('UIcon') as any, { name: icon as string, class: 'w-3 h-3 shrink-0' }) : null,
        h('span', { class: 'text-sm font-medium whitespace-nowrap' }, label)
      ].filter(Boolean))
    }

    // Footer: allow simple string footer values in column definitions.
    if (typeof processed.footer === 'string') {
      const footerLabel = processed.footer
      processed.footer = () => h('span', { class: 'text-sm font-semibold whitespace-nowrap' }, footerLabel)
    }
    return processed
  })
}

let lastColumnsRef: TableColumn<T>[] | null = null
let lastProcessedColumns: TableColumn<T>[] = []
const processedColumns = computed(() => {
  if (lastColumnsRef === props.columns) return lastProcessedColumns
  lastColumnsRef = props.columns
  lastProcessedColumns = processColumnDefinitions(props.columns) as TableColumn<T>[]
  return lastProcessedColumns
})


onMounted(() => {
  // Infinite Scroll logic for hybrid mode
  const scrollEl = table.value?.$el?.querySelector('.overflow-auto') || table.value?.$el
  if (scrollEl) {
    useInfiniteScroll(scrollEl, () => emit('load-more'),
      { distance: 200, canLoadMore: () => !props.loading && props.canLoadMore }
    )
  }
})

defineOptions({ inheritAttrs: false })
</script>
