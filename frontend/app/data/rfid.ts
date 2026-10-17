/**
 * RFID cards, scan history and gate command activity — types and API client.
 */

export interface RfidCard {
  cardUid: string
  licensePlate: string
  vehicleType: 'Car' | 'Motorcycle' | 'Truck'
  label?: string | null
  status: 'Active' | 'Blocked'
  lastUsedAt?: string | null
  createdAt: string
  updatedAt: string
}

export interface RfidCardList {
  data: RfidCard[]
  total: number
}

export interface RfidScanEvent {
  id: number
  cardUid: string
  gate: 'entry' | 'exit'
  licensePlate?: string | null
  sessionId?: string | null
  invoiceId?: string | null
  accepted: boolean
  reason?: string | null
  createdAt: string
}

export interface RfidScanList {
  data: RfidScanEvent[]
  total: number
}

export type GateCommandStatus = 'pending' | 'delivered' | 'acked' | 'failed' | 'expired'

export interface GateCommandState {
  commandId: string
  deviceCode: string
  command: string
  status: GateCommandStatus
  createdAt: string
  deliveredAt?: string | null
  ackedAt?: string | null
  expiresAt?: string | null
  message: string
}

export interface GateActivity {
  commands: GateCommandState[]
}

export interface RfidCardBody {
  cardUid: string
  licensePlate: string
  vehicleType: 'Car' | 'Motorcycle' | 'Truck'
  label?: string
}

export interface RfidCardUpdateBody {
  licensePlate?: string
  vehicleType?: 'Car' | 'Motorcycle' | 'Truck'
  label?: string
  status?: 'Active' | 'Blocked'
}

export const RFID_CARD_STATUS_ITEMS = [
  { label: 'All statuses', value: '' },
  { label: 'Active', value: 'Active' },
  { label: 'Blocked', value: 'Blocked' }
]

export const RFID_VEHICLE_TYPE_ITEMS = [
  { label: 'Car', value: 'Car' },
  { label: 'Motorcycle', value: 'Motorcycle' },
  { label: 'Truck', value: 'Truck' }
]

export const RFID_SCAN_GATE_ITEMS = [
  { label: 'All gates', value: '' },
  { label: 'Entry', value: 'entry' },
  { label: 'Exit', value: 'exit' }
]

export const RFID_SCAN_ACCEPTED_ITEMS = [
  { label: 'All results', value: '' },
  { label: 'Accepted', value: 'accepted' },
  { label: 'Rejected', value: 'rejected' }
]

export const GATE_COMMAND_STATUS_COLORS: Record<string, 'info' | 'warning' | 'success' | 'error' | 'neutral'> = {
  pending: 'info',
  delivered: 'warning',
  acked: 'success',
  failed: 'error',
  expired: 'neutral'
}

export async function fetchRfidCards(
  params: { search?: string, status?: string[], page?: number, limit?: number } = {},
  signal?: AbortSignal
): Promise<RfidCardList> {
  return useRfidApi().listCards(params, signal)
}

export async function registerRfidCard(body: RfidCardBody, signal?: AbortSignal): Promise<RfidCard> {
  return useRfidApi().registerCard(body, signal)
}

export async function updateRfidCard(
  cardUid: string,
  body: RfidCardUpdateBody,
  signal?: AbortSignal
): Promise<RfidCard> {
  return useRfidApi().updateCard(cardUid, body, signal)
}

export async function fetchRfidScans(
  params: { cardUid?: string, gate?: string, accepted?: boolean, page?: number, limit?: number } = {},
  signal?: AbortSignal
): Promise<RfidScanList> {
  return useRfidApi().listScans(params, signal)
}

export async function fetchGateActivity(
  params: { deviceCode?: string, limit?: number } = {},
  signal?: AbortSignal
): Promise<GateActivity> {
  return useRfidApi().gateActivity(params, signal)
}
