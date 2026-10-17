import { useApiConfig } from '~/composables/useApiConfig'
import type {
  GateActivity,
  RfidCard,
  RfidCardBody,
  RfidCardList,
  RfidCardUpdateBody,
  RfidScanList
} from '~/data/rfid'

export function useRfidApi() {
  const { apiUrl } = useApiConfig()

  async function listCards(
    params: { search?: string, status?: string[], page?: number, limit?: number } = {},
    signal?: AbortSignal
  ): Promise<RfidCardList> {
    return await $fetch<RfidCardList>(`${apiUrl.value}/api/rfid/cards`, {
      query: {
        ...(params.search ? { search: params.search } : {}),
        ...(params.status && params.status.length ? { status: params.status } : {}),
        page: params.page ?? 1,
        limit: params.limit ?? 100
      },
      signal
    })
  }

  async function registerCard(body: RfidCardBody, signal?: AbortSignal): Promise<RfidCard> {
    return await $fetch<RfidCard>(`${apiUrl.value}/api/rfid/cards`, {
      method: 'POST',
      body,
      signal
    })
  }

  async function updateCard(cardUid: string, body: RfidCardUpdateBody, signal?: AbortSignal): Promise<RfidCard> {
    return await $fetch<RfidCard>(`${apiUrl.value}/api/rfid/cards/${encodeURIComponent(cardUid)}`, {
      method: 'POST',
      body,
      signal
    })
  }

  async function listScans(
    params: { cardUid?: string, gate?: string, accepted?: boolean, page?: number, limit?: number } = {},
    signal?: AbortSignal
  ): Promise<RfidScanList> {
    return await $fetch<RfidScanList>(`${apiUrl.value}/api/rfid/scans`, {
      query: {
        ...(params.cardUid ? { cardUid: params.cardUid } : {}),
        ...(params.gate ? { gate: params.gate } : {}),
        ...(params.accepted !== undefined ? { accepted: params.accepted } : {}),
        page: params.page ?? 1,
        limit: params.limit ?? 100
      },
      signal
    })
  }

  async function gateActivity(
    params: { deviceCode?: string, limit?: number } = {},
    signal?: AbortSignal
  ): Promise<GateActivity> {
    return await $fetch<GateActivity>(`${apiUrl.value}/api/rfid/gate-activity`, {
      query: {
        ...(params.deviceCode ? { deviceCode: params.deviceCode } : {}),
        limit: params.limit ?? 50
      },
      signal
    })
  }

  return { listCards, registerCard, updateCard, listScans, gateActivity }
}
