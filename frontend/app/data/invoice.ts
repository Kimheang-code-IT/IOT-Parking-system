/**
 * Invoices — types, table config, and API client.
 */

export interface Invoice {
  id: string
  date: string
  plate: string
  amount: string
  method: 'Cash' | 'ABA' | 'KHQR'
  status: 'Paid' | 'Pending'
  entryTime?: string
  exitTime?: string
}

export interface InvoiceListResult {
  data: Invoice[]
  total: number
}

export interface InvoiceQuery extends Record<string, unknown> {
  page: number
  limit: number
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
  search?: string
  status?: string[]
  method?: string[]
}

export const INVOICE_COLUMNS = [
  { accessorKey: 'id', header: 'Invoice ID' },
  { accessorKey: 'date', header: 'Date' },
  { accessorKey: 'plate', header: 'License Plate' },
  { accessorKey: 'amount', header: 'Amount' },
  { accessorKey: 'method', header: 'Method' },
  { accessorKey: 'status', header: 'Status' }
]

export const INVOICE_STATUS_ITEMS = [
  { label: 'Paid', value: 'Paid', icon: 'i-lucide-circle-check', color: '#22c55e' },
  { label: 'Pending', value: 'Pending', icon: 'i-lucide-clock', color: '#f59e0b' }
]

export const INVOICE_METHOD_ITEMS = [
  { label: 'Cash', value: 'Cash', icon: 'i-lucide-banknote' },
  { label: 'ABA', value: 'ABA', icon: 'i-lucide-credit-card', color: '#3b82f6' },
  { label: 'KHQR', value: 'KHQR', icon: 'i-lucide-qr-code', color: '#8b5cf6' }
]

export async function fetchInvoices(query: InvoiceQuery, signal?: AbortSignal): Promise<InvoiceListResult> {
  return useInvoiceApi().list(query, signal)
}
