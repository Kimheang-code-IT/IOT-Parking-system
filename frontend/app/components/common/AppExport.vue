<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { DateFormatter, getLocalTimeZone, parseDate } from '@internationalized/date'
import { exportToCSV } from '~/utils/helpers/common'

type ExportRow = Record<string, any>
type DateRangeModel = {
  start: any
  end: any
}

interface Props {
  data?: ExportRow[]
  filename?: string
  dateField?: string
  title?: string
  fetchExportData?: (args: { startDate?: string; endDate?: string }) => Promise<ExportRow[]>
  label?: string
  icon?: string
  variant?: any
  showTrigger?: boolean
}

const modelValue = defineModel<boolean>('open')

const props = withDefaults(defineProps<Props>(), {
  data: () => [],
  filename: 'export',
  dateField: '',
  title: '',
  label: 'Export',
  icon: 'i-lucide-download',
  variant: 'ghost',
  showTrigger: true
})

const { t, locale } = useI18n()
const { formattedRange } = useGlobalFilter()

const internalOpen = ref(false)
const open = computed({
  get: () => modelValue.value !== undefined ? modelValue.value : internalOpen.value,
  set: (val) => {
    if (modelValue.value !== undefined) modelValue.value = val
    else internalOpen.value = val
  }
})

const df = computed(() => new DateFormatter(locale.value, { month: 'short', day: 'numeric', year: 'numeric' }))

const localRange = ref({
  start: undefined,
  end: undefined,
} as DateRangeModel)

function syncRangeFromGlobal() {
  localRange.value = {
    start: formattedRange.value.start ? parseDate(formattedRange.value.start) : undefined,
    end: formattedRange.value.end ? parseDate(formattedRange.value.end) : undefined
  }
}

watch(open, (val) => {
  if (val) syncRangeFromGlobal()
})

const isLoading = ref(false)

function toValidDate(raw: unknown): Date | null {
  if (raw instanceof Date) {
    return Number.isNaN(raw.getTime()) ? null : raw
  }
  if (typeof raw === 'string' || typeof raw === 'number') {
    const d = new Date(raw)
    return Number.isNaN(d.getTime()) ? null : d
  }
  return null
}

const exportData = computed(() => {
  if (!props.data?.length) return []
  if (!props.dateField || (!localRange.value.start && !localRange.value.end)) {
    return props.data
  }
  const tz = getLocalTimeZone()
  const start = localRange.value.start?.toDate(tz)
  const end = localRange.value.end?.toDate(tz)

  return props.data.filter(row => {
    const rowDate = toValidDate(row[props.dateField!])
    if (!rowDate) return true
    if (start && rowDate < start) return false
    if (end && rowDate > end) return false
    return true
  })
})

const recordCount = computed(() => exportData.value.length)

const dateRangeLabel = computed(() => {
  const s = localRange.value.start
  const e = localRange.value.end
  const tz = getLocalTimeZone()
  if (s && e) return `${df.value.format(s.toDate(tz))} → ${df.value.format(e.toDate(tz))}`
  if (s) return `${df.value.format(s.toDate(tz))}`
  return 'All Dates'
})

function resetRange() {
  localRange.value = { start: undefined, end: undefined }
}

async function handleExport() {
  if (!exportData.value.length && !props.fetchExportData) return
  isLoading.value = true
  try {
    const name = `${props.filename}_${new Date().toISOString().slice(0, 10)}`
    const tz = getLocalTimeZone()
    const rows = props.fetchExportData
      ? await props.fetchExportData({
          startDate: localRange.value.start?.toDate(tz)?.toISOString(),
          endDate: localRange.value.end?.toDate(tz)?.toISOString()
        })
      : exportData.value
    if (!rows.length) return
    // Avoid long main-thread block for huge arrays by yielding once.
    await new Promise<void>((resolve) => setTimeout(resolve, 0))
    exportToCSV(rows, `${name}.csv`)
    open.value = false
  } finally {
    isLoading.value = false
  }
}

function onClose() {
  open.value = false
}
</script>

<template>
  <div class="inline-block">
    <UButton
      v-if="showTrigger"
      :icon="icon"
      :color="variant === 'ghost' ? 'neutral' : 'primary'"
      :variant="variant"
      :label="label"
      @click="open = true"
    />

    <UModal :dismissible="false"
      v-model:open="open"
      :ui="{ content: 'max-w-md w-[95vw] sm:w-full', header: 'border-none p-0' }"
    >
    <template #header>
      <div class="flex items-center justify-between w-full px-4 pt-4">
        <div class="flex items-center gap-2.5">
          <div class="size-9 rounded-lg flex items-center justify-center">
            <UIcon name="i-lucide-folder-down" class="text-primary size-8" />
          </div>
          <div>
            <h2 class="text-lg font-bold text-highlighted tracking-tight">
              {{ title || "Export" }}
            </h2>
          </div>
        </div>
        <UButton icon="i-lucide-x" color="neutral" variant="ghost" size="sm" @click="onClose" />
      </div>
    </template>

    <template #body>
      <div class="px-4 space-y-4">

        <!-- Date Range Picker -->
        <div class="space-y-2">
          <div class="border border-default rounded-xl overflow-hidden bg-muted/10">
            <UCalendar
              v-model="localRange"
              class="p-2 w-full"
              :number-of-months="1"
              range
            />
            <div class="px-3 pb-3 pt-1 border-t border-default flex items-center justify-between gap-2">
              <div class="flex items-center gap-1.5 text-xs text-muted-foreground">
                <span class="i-lucide-calendar-range size-3.5" />
                <span>{{ dateRangeLabel }}</span>
              </div>
              <UButton
                size="xs"
                variant="ghost"
                color="neutral"
                icon="i-lucide-rotate-ccw"
                :label="'Reset'"
                @click="resetRange"
              />
            </div>
          </div>
        </div>

        <div class="space-y-1">
          <div
            class="flex items-center gap-2.5 px-4 py-3 rounded-lg border border-primary bg-primary/8 text-primary text-sm font-medium"
          >
            <span class="i-lucide-file-spreadsheet size-5 shrink-0" />
            <span>{{ 'Export Format' }}</span>
            <span class="i-lucide-check size-4 ml-auto" />
          </div>
        </div>
      </div>
    </template>

    <template #footer>
      <div class="flex items-center justify-end gap-2 w-full">
        <UButton
          :label="'Cancel'"
          color="neutral"
          variant="soft"
          size="md"
          class="font-semibold"
          @click="onClose"
        />
        <UButton
          :label="'Export'"
          color="primary"
          variant="solid"
          size="md"
          icon="i-lucide-download"
          class="font-semibold"
          :loading="isLoading"
          :disabled="recordCount === 0"
          @click="handleExport"
        />
      </div>
    </template>
  </UModal>
  </div>
</template>
