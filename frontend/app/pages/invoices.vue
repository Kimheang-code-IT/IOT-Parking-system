<script setup lang="ts">
import { useInvoice } from '~/composables/table/useInvoice'
import { useInvoicePreview } from '~/composables/table/useInvoicePreview'
import { TABLE_PANEL_UI, TABLE_PAGE_BODY_CLASS } from '~/utils/tablePanelLayout'

const { isOpen: isInvoiceOpen, invoiceData, barcodeLoading, openPreview, printInvoice } = useInvoicePreview()

const {
  invoices,
  columns,
  searchQuery,
  selectedStatus,
  statusItems,
  selectedMethod,
  methodItems,
  isLoading
} = useInvoice()

async function handleShowInvoice(invoice: any) {
  await openPreview({
    invoiceNo: invoice.id,
    plateNumber: invoice.plate,
    vehicleType: 'Unknown',
    entryTime: invoice.entryTime ?? invoice.date,
    exitTime: invoice.exitTime ?? new Date().toISOString(),
    duration: 'N/A',
    amount: parseFloat(invoice.amount.replace('$', '')),
    paymentMethod: invoice.method,
    date: invoice.date
  })
}
</script>

<template>
  <UDashboardPanel id="invoices" :ui="TABLE_PANEL_UI">
    <template #header>
      <UDashboardNavbar title="Parking Invoices">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <div class="flex items-center gap-2">
            <CommonAppDatepicker />
            <CommonAppExport
              :data="invoices"
              variant="solid"
              filename="parking_invoices"
              date-field="date"
              title="Export Invoices"
            />
          </div>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div :class="TABLE_PAGE_BODY_CLASS">
        <TableApptable
          v-model:global-filter="searchQuery"
          v-model:filter-value="selectedStatus"
          v-model:filter-value-secondary="selectedMethod"
          :filter-items="statusItems"
          filter-placeholder="Status"
          :filter-items-secondary="methodItems"
          filter-placeholder-secondary="Method"
          :data="invoices"
          :columns="columns"
          :loading="isLoading"
          title="Recent Billing Invoices"
        >
          <template #id-cell="{ row }">
            <div class="group flex items-center gap-2 font-bold">
              <span>{{ row.getValue('id') }}</span>
              <UButton
                icon="i-lucide-receipt-text"
                variant="ghost"
                color="primary"
                size="xs"
                @click.stop="handleShowInvoice(row.original)"
              />
            </div>
          </template>
        </TableApptable>
      </div>
    </template>
  </UDashboardPanel>

  <!-- Invoice Preview Modal -->
  <CommonAppInvoicePreview
    v-model="isInvoiceOpen"
    :data="invoiceData"
    :barcode-loading="barcodeLoading"
    @print="printInvoice"
  />
</template>