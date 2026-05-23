import type { ParkingListResult, ParkingQuery } from '~/data/parking'
import { useApiConfig } from '~/composables/useApiConfig'
import { toListQuery } from '~/utils/listQuery'

export function useParkingApi() {
  const { apiUrl } = useApiConfig()

  async function list(query: ParkingQuery, signal?: AbortSignal): Promise<ParkingListResult> {
    return await $fetch<ParkingListResult>(`${apiUrl.value}/api/parking`, {
      query: toListQuery(query),
      signal
    })
  }

  return { list }
}
