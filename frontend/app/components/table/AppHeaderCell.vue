<template>
  <button
    v-bind="$attrs"
    :class="[
      'group flex items-center gap-1.5 w-full text-left',
      canSort ? 'cursor-pointer select-none' : 'cursor-default'
    ]"
    @click="handleClick"
  >
    <UIcon v-if="icon" :name="icon" class="w-3.5 h-3.5 shrink-0 text-muted-foreground/50" />
    
    <span class="text-sm font-medium leading-[13px] whitespace-nowrap tracking-tight">
      {{ label }}
    </span>

    <div v-if="canSort" class="flex items-center gap-[2px] ml-1">
      <span v-if="sortIndex !== -1 && multiSortCount > 1" class="text-[10px] font-normal text-primary mt-px">
        {{ sortIndex + 1 }}
      </span>
      <UIcon 
        :name="sortIcon"
        :class="[
          'w-3 h-3 shrink-0 transition-colors',
          isSorted ? 'text-primary' : 'text-muted-foreground/30 group-hover:text-muted-foreground/60'
        ]"
      />
    </div>
  </button>
</template>

<script setup lang="ts" generic="TData, TValue">
import { computed } from 'vue'
import type { Column } from '@tanstack/vue-table'

const props = defineProps<{
  column: Column<TData, TValue>
  label: string
  icon?: string
  multiSortCount: number
}>()

const canSort = computed(() => props.column.getCanSort())
const isSorted = computed(() => props.column.getIsSorted())
const sortIndex = computed(() => props.column.getSortIndex())

const sortIcon = computed(() => {
  if (isSorted.value === 'asc') return 'i-lucide-arrow-up'
  if (isSorted.value === 'desc') return 'i-lucide-arrow-down'
  return 'i-lucide-arrow-down-up'
})

function handleClick(e: MouseEvent) {
  if (!canSort.value) return
  // toggleSorting(desc?: boolean, isMulti?: boolean)
  // If e.shiftKey is true, it preserves other sorts.
  props.column.toggleSorting(isSorted.value === 'asc', e.shiftKey)
}
</script>
