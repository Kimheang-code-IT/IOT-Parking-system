/**
 * Dashboard — types and API client (aggregates from PostgreSQL via FastAPI).
 */

export interface DashboardStat {
  label: string
  value: string
  icon: string
}

export interface TrendPoint {
  name: string
  value: number
}

export interface VehicleTypePoint {
  name: string
  value: number
}

export interface PeakHoursData {
  labels: string[]
  values: number[]
}

export interface InteractiveChartData {
  source: (string | number)[][]
}

export async function fetchDashboardStats(signal?: AbortSignal): Promise<DashboardStat[]> {
  const { apiUrl } = useApiConfig()
  return await $fetch<DashboardStat[]>(`${apiUrl.value}/api/dashboard/stats`, { signal })
}

export async function fetchOccupancyTrend(signal?: AbortSignal): Promise<TrendPoint[]> {
  const { apiUrl } = useApiConfig()
  return await $fetch<TrendPoint[]>(`${apiUrl.value}/api/dashboard/occupancy-trend`, { signal })
}

export async function fetchVehicleTypes(signal?: AbortSignal): Promise<VehicleTypePoint[]> {
  const { apiUrl } = useApiConfig()
  return await $fetch<VehicleTypePoint[]>(`${apiUrl.value}/api/dashboard/vehicle-types`, { signal })
}

export async function fetchPeakHours(signal?: AbortSignal): Promise<PeakHoursData> {
  const { apiUrl } = useApiConfig()
  return await $fetch<PeakHoursData>(`${apiUrl.value}/api/dashboard/peak-hours`, { signal })
}

export async function fetchInteractiveChart(vehicleType?: string, signal?: AbortSignal): Promise<InteractiveChartData> {
  const { apiUrl } = useApiConfig()
  const params = vehicleType ? `?vehicle_type=${encodeURIComponent(vehicleType)}` : ''
  return await $fetch<InteractiveChartData>(`${apiUrl.value}/api/dashboard/interactive-chart${params}`, { signal })
}
