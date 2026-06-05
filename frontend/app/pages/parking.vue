<script setup lang="ts">
import { useParkingHistory } from '~/composables/table/useParking'

const {
  entries,
  columns,
  pending,
  searchQuery,
  selectedStatus,
  selectedType,
  statusItems,
  typeItems,
  entryDateRange,
  exitDateRange
} = useParkingHistory()
</script>

<template>
  <UDashboardPanel id="parking">
    <template #header>
      <UDashboardNavbar title="Parking History">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <div class="flex items-center gap-2">
            <!-- Entry Time Date Picker -->
            <div class="flex items-center gap-1.5">
              <span class="text-xs text-muted-foreground font-medium hidden sm:inline">Entry</span>
              <CommonAppDatepicker
                :range="entryDateRange"
                @update:range="entryDateRange = $event"
              />
            </div>
            <!-- Exit Time Date Picker -->
            <div class="flex items-center gap-1.5">
              <span class="text-xs text-muted-foreground font-medium hidden sm:inline">Exit</span>
              <CommonAppDatepicker
                :range="exitDateRange"
                @update:range="exitDateRange = $event"
              />
            </div>
            <CommonAppExport
              :data="entries"
              variant="solid"
              filename="parking_history"
              date-field="entryTime"
              title="Export Parking History"
            />
          </div>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div class="-m-4">
        <TableApptable
          v-model:global-filter="searchQuery"
          v-model:filter-value="selectedStatus"
          v-model:filter-value-secondary="selectedType"
          v-model:filter-items="statusItems"
          filter-placeholder="Status"
          v-model:filter-items-secondary="typeItems"
          filter-placeholder-secondary="Vehicle Type"
          :data="entries"
          :columns="columns"
          :loading="pending"
          title="Vehicle Entry/Exit History"
        />
      </div>
    </template>
  </UDashboardPanel>
</template>
