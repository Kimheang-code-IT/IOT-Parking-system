<script setup lang="ts">
const { t } = useI18n()
const { dateRange: globalRange, resetRange: globalReset } = useGlobalFilter()

const props = defineProps<{
  range?: { start: any; end: any }
}>()

const emit = defineEmits<{
  (e: 'update:range', val: { start: any; end: any }): void
}>()

const dateRange = computed({
  get: () => props.range !== undefined ? props.range : globalRange.value,
  set: (val) => {
    if (props.range !== undefined) emit('update:range', val)
    else globalRange.value = val
  }
})

const resetRange = () => {
  if (props.range !== undefined) emit('update:range', { start: undefined, end: undefined })
  else globalReset()
}

function formatRangeDate(value: { toString: () => string } | undefined) {
  if (!value) return ''
  return new Date(value.toString()).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric'
  })
}
</script>

<template>
  <UPopover :content="{ align: 'end' }">
    <!-- Trigger Button — works on all screen sizes -->
    <UButton
      color="neutral"
      variant="subtle"
      icon="i-lucide-calendar"
      trailing-icon="i-lucide-chevron-down"
      class="shrink-0 font-normal"
    >
      <span class="hidden sm:inline-flex items-center gap-1 ml-1.5">
        <template v-if="dateRange.start">
          <template v-if="dateRange.end">
            <span class="text-xs opacity-70">{{ formatRangeDate(dateRange.start) }}</span>
            <span class="mx-1 text-primary">→</span>
            <span class="text-xs font-bold">{{ formatRangeDate(dateRange.end) }}</span>
          </template>
          <template v-else>
            {{ formatRangeDate(dateRange.start) }}
          </template>
        </template>
        <template v-else>
          Date Picker
        </template>
      </span>
    </UButton>

    <template #content>
      <div class="flex flex-col bg-background rounded-lg overflow-hidden min-w-[200px]">
        <!-- Calendar — 1 month on mobile, 2 on lg screens -->
        <UCalendar
          v-model="dateRange"
          class="p-2"
          :number-of-months="1"
          range
        />
        <!-- Sidebar panel -->
        <div class="p-4 bg-muted/20 border-t flex flex-col gap-2 justify-end">
          <UButton
            label="Reset"
            size="xs"
            variant="ghost"
            color="neutral"
            icon="i-lucide-rotate-ccw"
            @click="resetRange"
          />
        </div>
      </div>
    </template>
  </UPopover>
</template>
