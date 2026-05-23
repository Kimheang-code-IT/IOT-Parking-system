import { nextTick, ref } from 'vue'
import { useInvoiceApi } from '~/composables/useInvoiceApi'

export interface InvoiceData {
  invoiceNo: string
  plateNumber: string
  vehicleType: string
  entryTime: string
  exitTime: string
  duration: string
  amount: number
  paymentMethod: string
  date: string
  verifyHash?: string
  barcodeImage?: string
}

export function useInvoicePreview() {
  const isOpen = ref(false)
  const invoiceData = ref<InvoiceData | null>(null)
  const barcodeLoading = ref(false)

  async function openPreview(data: InvoiceData) {
    invoiceData.value = { ...data, verifyHash: undefined, barcodeImage: undefined }
    isOpen.value = true
    barcodeLoading.value = true
    try {
      const barcode = await useInvoiceApi().getExitBarcode(data.invoiceNo)
      if (invoiceData.value?.invoiceNo === data.invoiceNo) {
        invoiceData.value = {
          ...invoiceData.value,
          verifyHash: barcode.verifyHash,
          barcodeImage: barcode.barcodeImage
        }
      }
    } catch (err) {
      console.error('Failed to load exit barcode:', err)
    } finally {
      barcodeLoading.value = false
    }
  }

  function closePreview() {
    isOpen.value = false
  }

  function printInvoice() {
    if (!import.meta.client) return
    nextTick(() => {
      window.print()
    })
  }

  return {
    isOpen,
    invoiceData,
    barcodeLoading,
    openPreview,
    closePreview,
    printInvoice
  }
}
