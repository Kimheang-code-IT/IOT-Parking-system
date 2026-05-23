<script setup lang="ts">
import { useParkingDashboard } from '~/composables/table/useParking'

const {
  stats: summaryStats,
  occupancyTrend,
  vehicleTypes,
  peakHours,
  pending
} = useParkingDashboard()

// Keep dashboard charts large and balanced across screen sizes.
const SECTION_HEIGHT = {
  DASHBOARD: "clamp(560px, calc(100vh - 220px), 760px)",
};

type PieDataPoint = { name: string; value: number };
type BarDataPoint = { labels: string[]; values: number[] };

const occupancyChartData = computed<BarDataPoint>(() => ({
  labels: occupancyTrend.value.map(d => d.name),
  values: occupancyTrend.value.map(d => d.value)
}));
const vehiclePieData = computed<PieDataPoint[]>(() => vehicleTypes.value);
const peakHoursBarData = computed<BarDataPoint>(() => peakHours.value);
</script>
<template>
  <UDashboardPanel id="dashboard">
    <template #header>
      <UDashboardNavbar title="Parking Dashboard">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="-m-4 space-y-3">
        <!-- Top Summary Cards -->
        <UPageGrid class="grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <template v-if="pending">
            <UCard v-for="i in 4" :key="i" class="shadow-sm border-accented">
              <div class="flex items-center gap-3">
                <USkeleton class="size-10 rounded-lg" />
                <div class="space-y-2 flex-1">
                  <USkeleton class="h-4 w-1/2" />
                  <USkeleton class="h-6 w-3/4" />
                </div>
              </div>
            </UCard>
          </template>
          <template v-else>
            <template v-for="(stat, idx) in summaryStats" :key="idx">
              <UCard class="shadow-sm border-accented">
                <div class="flex items-center gap-3">
                  <div class="p-2 bg-primary/10 rounded-lg">
                    <UIcon :name="stat.icon" class="size-6 text-primary" />
                  </div>
                  <div class="min-w-0 flex-1">
                    <p class="text-sm font-bold text-muted-foreground text-gray-500">
                      {{ stat.label }}
                    </p>
                    <h3 class="text-2xl font-black tracking-tight text-foreground truncate">
                      {{ stat.value }}
                    </h3>
                  </div>
                </div>
              </UCard>
            </template>
          </template>
        </UPageGrid>

        <!-- Bottom Grid: Interactive Summary Report -->
        <div class="pb-4">
          <UCard class="shadow-sm border-accented flex flex-col overflow-hidden"
            :style="{ minHeight: '600px' }" :ui="{ body: 'p-4 flex-1 min-h-0' }">
            <template #header>
              <div class="flex items-center gap-2">
                <UIcon name="i-lucide-activity" class="size-5 text-primary" />
                <h2 class="font-normal text-foreground">
                  Interactive Parking Performance Analysis
                </h2>
              </div>
            </template>
            <div class="w-full h-full relative transition-all duration-300 flex-1 min-h-0">
              <LazyChartAppChartInteractive>
                <template #fallback>
                  <div
                    class="absolute inset-0 flex flex-col gap-2 p-4 z-10 bg-background/50 backdrop-blur-[2px]">
                    <USkeleton v-for="i in 15" :key="i" class="h-4 w-full" />
                  </div>
                </template>
              </LazyChartAppChartInteractive>
            </div>
          </UCard>
        </div>
      </div>
    </template>
  </UDashboardPanel>
</template>
