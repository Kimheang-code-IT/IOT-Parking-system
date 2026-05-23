/**
 * Parking history — types, table config, and API client.
 */

export interface ParkingEntry {
  id: string
  licensePlate: string
  type: 'Car' | 'Motorcycle' | 'Truck'
  entryTime: string
  exitTime: string
  duration: string
  status: 'Active' | 'Completed'
}

export interface ParkingListResult {
  data: ParkingEntry[]
  total: number
}

export interface ParkingQuery extends Record<string, unknown> {
  page: number
  limit: number
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
  search?: string
  status?: string[]
  type?: string[]
  entryDateFrom?: string
  entryDateTo?: string
  exitDateFrom?: string
  exitDateTo?: string
}

export const PARKING_COLUMNS = [
  { accessorKey: 'id', header: 'ID' },
  { accessorKey: 'licensePlate', header: 'License Plate' },
  { accessorKey: 'type', header: 'Type' },
  { accessorKey: 'entryTime', header: 'Entry Time' },
  { accessorKey: 'exitTime', header: 'Exit Time' },
  { accessorKey: 'duration', header: 'Duration' },
  { accessorKey: 'status', header: 'Status' }
]

export const PARKING_STATUS_ITEMS = [
  { label: 'Active', value: 'Active', icon: 'i-lucide-circle-dot', color: '#22c55e' },
  { label: 'Completed', value: 'Completed', icon: 'i-lucide-circle-check', color: '#3b82f6' }
]

export const PARKING_TYPE_ITEMS = [
  { label: 'Car', value: 'Car', icon: 'i-lucide-car' },
  { label: 'Motorcycle', value: 'Motorcycle', icon: 'i-lucide-bike' },
  { label: 'Truck', value: 'Truck', icon: 'i-lucide-truck' }
]

export async function fetchParkingEntries(query: ParkingQuery, signal?: AbortSignal): Promise<ParkingListResult> {
  return useParkingApi().list(query, signal)
}
