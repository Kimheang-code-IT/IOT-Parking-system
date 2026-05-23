/**
 * Invoice composable — data from FastAPI / PostgreSQL.
 */
import { ref, computed } from 'vue'
import { useServerTableResource } from '~/composables/table/useServerTableResource'
import {
  INVOICE_COLUMNS,
  INVOICE_STATUS_ITEMS,
  INVOICE_METHOD_ITEMS,
  fetchInvoices,
  type Invoice,
  type InvoiceQuery
} from '~/data/invoice'

export function useInvoice() {
  const searchQuery = ref('')
  const selectedStatus = ref<string[]>([])
  const selectedMethod = ref<string[]>([])

  const serverQuery = computed<InvoiceQuery>(() => ({
    page: 1,
    limit: 50,
    search: searchQuery.value || undefined,
    status: selectedStatus.value.length ? selectedStatus.value : undefined,
    method: selectedMethod.value.length ? selectedMethod.value : undefined
  }))

  const { rows: invoices, isLoading } = useServerTableResource<Invoice, InvoiceQuery>({
    resourceKey: 'invoices',
    serverQuery,
    listFn: (query, signal) => fetchInvoices(query, signal)
  })

  return {
    invoices,
    columns: INVOICE_COLUMNS,
    searchQuery,
    selectedStatus,
    statusItems: INVOICE_STATUS_ITEMS,
    selectedMethod,
    methodItems: INVOICE_METHOD_ITEMS,
    isLoading
  }
}
