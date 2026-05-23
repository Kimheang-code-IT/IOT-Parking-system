import { computed, onBeforeUnmount, onMounted, ref, watch, type Ref } from 'vue'
import { useQueryClient } from '~/composables/data/useQueryClient'

type ListResult<T> = {
  data?: T[]
  total?: number
  aggregates?: Record<string, number>
}

interface ServerTableResourceOptions<T, Q extends Record<string, unknown>> {
  resourceKey: string
  serverQuery: Ref<Q>
  listFn: (query: Q, signal?: AbortSignal) => Promise<ListResult<T>>
  debounceMs?: number
}

export function useServerTableResource<T, Q extends Record<string, unknown>>(options: ServerTableResourceOptions<T, Q>) {
  const rows = ref<T[]>([]) as Ref<T[]>
  const totalRows = ref(0)
  const isLoading = ref(false)
  const aggregates = ref<Record<string, number>>({})
  const queryClient = useQueryClient()
  const debounceMs = options.debounceMs ?? 200
  let timer: ReturnType<typeof setTimeout> | null = null
  let controller: AbortController | null = null

  const queryKey = computed(() => `${options.resourceKey}:${JSON.stringify(options.serverQuery.value)}`)

  async function load() {
    controller?.abort()
    controller = new AbortController()
    isLoading.value = true
    try {
      const result = await queryClient.getOrFetch<ListResult<T>>(
        queryKey.value,
        () => options.listFn(options.serverQuery.value, controller?.signal),
        5000
      )
      rows.value = result.data || []
      totalRows.value = result.total ?? rows.value.length
      aggregates.value = result.aggregates || {}
    } catch (err: any) {
      if (err.name === 'AbortError' || err.message?.includes('aborted')) {
        return
      }
      console.error('Failed to load resource:', err)
      rows.value = []
      totalRows.value = 0
    } finally {
      isLoading.value = false
    }
  }

  function refresh() {
    queryClient.invalidate(options.resourceKey)
    return load()
  }

  function scheduleLoad() {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      load()
    }, debounceMs)
  }

  onMounted(load)
  watch(options.serverQuery, scheduleLoad, { deep: true })
  onBeforeUnmount(() => {
    if (timer) clearTimeout(timer)
    controller?.abort()
  })

  return {
    rows,
    totalRows,
    isLoading,
    aggregates,
    load,
    refresh
  }
}
