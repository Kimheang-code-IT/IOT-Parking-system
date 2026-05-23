import type { InvoiceListResult, InvoiceQuery } from '~/data/invoice'
import { useApiConfig } from '~/composables/useApiConfig'
import { toListQuery } from '~/utils/listQuery'

export interface InvoiceExitBarcode {
  invoiceId: string
  verifyHash: string
  barcodeImage: string
  plate: string
}

export function useInvoiceApi() {
  const { apiUrl } = useApiConfig()

  async function list(query: InvoiceQuery, signal?: AbortSignal): Promise<InvoiceListResult> {
    return await $fetch<InvoiceListResult>(`${apiUrl.value}/api/invoices`, {
      query: toListQuery(query),
      signal
    })
  }

  async function getExitBarcode(invoiceId: string, signal?: AbortSignal): Promise<InvoiceExitBarcode> {
    return await $fetch<InvoiceExitBarcode>(
      `${apiUrl.value}/api/invoices/${encodeURIComponent(invoiceId)}/exit-barcode`,
      { signal }
    )
  }

  return { list, getExitBarcode }
}
