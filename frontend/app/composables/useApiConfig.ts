/**
 * API base URL for FastAPI backend (from runtimeConfig or override).
 */
import { ref, computed } from 'vue'

const apiUrlOverride = ref<string | null>(null)

/** Normalizes a base URL so it can be concatenated with '/api/...':
 *   'http://host:8000/' -> 'http://host:8000'   (absolute)
 *   '/'                 -> ''                    (same-origin, reverse proxy)
 */
function normalizeApiUrl(url: string): string {
  return url.trim().replace(/\/+$/, '')
}

export function useApiConfig() {
  const config = useRuntimeConfig()

  const apiUrl = computed({
    get: () => apiUrlOverride.value ?? normalizeApiUrl(config.public.apiUrl as string),
    set: (value: string) => {
      apiUrlOverride.value = normalizeApiUrl(value)
    }
  })

  function setApiUrl(url: string) {
    apiUrlOverride.value = normalizeApiUrl(url)
  }

  return {
    apiUrl,
    setApiUrl
  }
}
