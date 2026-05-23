/**
 * Parking composables — all data from FastAPI / PostgreSQL.
 */
import { ref, computed, onMounted } from 'vue'
import { useServerTableResource } from '~/composables/table/useServerTableResource'
import { useApiConfig } from '~/composables/useApiConfig'
import {
  fetchDashboardStats,
  fetchOccupancyTrend,
  fetchVehicleTypes,
  fetchPeakHours,
  type DashboardStat,
  type TrendPoint,
  type VehicleTypePoint,
  type PeakHoursData
} from '~/data/dashboard'
import {
  PARKING_COLUMNS,
  PARKING_STATUS_ITEMS,
  PARKING_TYPE_ITEMS,
  fetchParkingEntries,
  type ParkingEntry,
  type ParkingQuery
} from '~/data/parking'

export function useParkingDashboard() {
  const { apiUrl } = useApiConfig()
  const pending = ref(false)

  const stats = ref<DashboardStat[]>([])
  const occupancyTrend = ref<TrendPoint[]>([])
  const vehicleTypes = ref<VehicleTypePoint[]>([])
  const peakHours = ref<PeakHoursData>({ labels: [], values: [] })

  async function refresh() {
    pending.value = true
    try {
      const [statsData, trendData, typesData, peakData] = await Promise.all([
        fetchDashboardStats(),
        fetchOccupancyTrend(),
        fetchVehicleTypes(),
        fetchPeakHours()
      ])
      stats.value = statsData
      occupancyTrend.value = trendData
      vehicleTypes.value = typesData
      peakHours.value = peakData
    } catch (err) {
      console.error('Dashboard load failed:', err)
    } finally {
      pending.value = false
    }
  }

  onMounted(() => {
    refresh()
  })

  return {
    stats,
    occupancyTrend,
    vehicleTypes,
    peakHours,
    pending,
    apiUrl,
    refresh
  }
}

export function useParkingHistory() {
  const searchQuery = ref('')
  const selectedStatus = ref<string[]>([])
  const selectedType = ref<string[]>([])

  const entryDateRange = ref<{ start: any; end: any }>({ start: undefined, end: undefined })
  const exitDateRange = ref<{ start: any; end: any }>({ start: undefined, end: undefined })

  function toIso(val: any): string | undefined {
    if (!val) return undefined
    return new Date(val.toString()).toISOString().split('T')[0]
  }

  const serverQuery = computed<ParkingQuery>(() => ({
    page: 1,
    limit: 50,
    search: searchQuery.value || undefined,
    status: selectedStatus.value.length ? selectedStatus.value : undefined,
    type: selectedType.value.length ? selectedType.value : undefined,
    entryDateFrom: toIso(entryDateRange.value.start),
    entryDateTo: toIso(entryDateRange.value.end),
    exitDateFrom: toIso(exitDateRange.value.start),
    exitDateTo: toIso(exitDateRange.value.end)
  }))

  const { rows: entries, isLoading: pending } = useServerTableResource<ParkingEntry, ParkingQuery>({
    resourceKey: 'parking-history',
    serverQuery,
    listFn: (query, signal) => fetchParkingEntries(query, signal)
  })

  return {
    entries,
    columns: PARKING_COLUMNS,
    pending,
    searchQuery,
    selectedStatus,
    selectedType,
    statusItems: PARKING_STATUS_ITEMS,
    typeItems: PARKING_TYPE_ITEMS,
    entryDateRange,
    exitDateRange
  }
}
