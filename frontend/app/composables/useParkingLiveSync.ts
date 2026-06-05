/**
 * Poll API revision; when parking data changes (gate entry/exit), run refresh callbacks.
 */
import { onBeforeUnmount, onMounted } from 'vue'
import { useApiConfig } from '~/composables/useApiConfig'
import { useQueryClient } from '~/composables/data/useQueryClient'

type RefreshFn = () => void | Promise<void>

export function useParkingLiveSync(refreshFns: RefreshFn | RefreshFn[], intervalMs = 3000) {
  const { apiUrl } = useApiConfig()
  const queryClient = useQueryClient()
  let lastRevision = 0
  let timer: ReturnType<typeof setInterval> | null = null

  const fns = Array.isArray(refreshFns) ? refreshFns : [refreshFns]

  async function poll() {
    try {
      const res = await $fetch<{ revision: number }>(`${apiUrl.value}/api/dashboard/revision`)
      const rev = res.revision
      if (lastRevision > 0 && rev !== lastRevision) {
        queryClient.invalidate('parking-history')
        for (const fn of fns) {
          await fn()
        }
      }
      lastRevision = rev
    } catch {
      /* API offline */
    }
  }

  onMounted(() => {
    void poll()
    timer = setInterval(() => void poll(), intervalMs)
  })

  onBeforeUnmount(() => {
    if (timer) clearInterval(timer)
  })
}
