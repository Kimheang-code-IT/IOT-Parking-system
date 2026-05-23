/**
 * API base URL for FastAPI backend (from runtimeConfig or override).
 */
import { ref, computed } from 'vue'

const apiUrlOverride = ref<string | null>(null)

export function useApiConfig() {
  const config = useRuntimeConfig()

  const apiUrl = computed({
    get: () => apiUrlOverride.value ?? (config.public.apiUrl as string),
    set: (value: string) => {
      apiUrlOverride.value = value.trim()
    }
  })

  function setApiUrl(url: string) {
    apiUrlOverride.value = url.trim()
  }

  return {
    apiUrl,
    setApiUrl
  }
}
