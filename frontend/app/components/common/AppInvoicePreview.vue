<script setup lang="ts">
import type { InvoiceData } from '~/composables/table/useInvoicePreview'
import receiptLogo from '~/assets/image/logo.png'
import { formatReceiptDate, formatReceiptFrom, formatReceiptTo } from '~/utils/format/receiptDate'

const props = defineProps<{
  modelValue: boolean
  data: InvoiceData | null
  barcodeLoading?: boolean
}>()

const emit = defineEmits(['update:modelValue', 'print'])

const isOpen = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const receiptDate = computed(() => formatReceiptDate(props.data?.date))
const receiptFrom = computed(() => formatReceiptFrom(props.data?.entryTime))
const receiptTo = computed(() => formatReceiptTo(props.data?.exitTime))
const receiptMethod = computed(() => {
  const m = props.data?.paymentMethod?.trim()
  if (!m) return 'CASH'
  if (m.toUpperCase() === 'ABA' || m.toUpperCase() === 'KHQR') return 'ABA PAY'
  return m.toUpperCase()
})

function handlePrint() {
  emit('print')
}
</script>

<template>
  <UModal
    v-model:open="isOpen"
    :dismissible="false"
    :ui="{ content: 'w-[80mm] max-w-[80mm] p-0' }"
  >
    <template #content>
      <div
        id="receipt-print-root"
        class="receipt-print-root bg-white p-4 font-mono text-[11px] leading-snug text-slate-800 select-none sm:p-5"
      >
        <div class="mb-4 flex items-start justify-between gap-2">
          <div class="size-14 shrink-0">
            <img :src="receiptLogo" alt="The Parking" class="size-full object-contain grayscale">
          </div>
          <div class="min-w-0 text-right text-[9px] leading-tight">
            <p class="text-[14px] font-bold uppercase tracking-tight">IOT PARKING SYSTEM</p>
            <p class="text-[12px]">123 Smart St, Tech City</p>
            <p class="text-[12px]">Tel: +855 12 345 678</p>
          </div>
        </div>

        <p class="mb-3 text-center tracking-tighter opacity-50">
          ****************************************
        </p>

        <h2
          class="mb-4 text-center text-sm font-black uppercase tracking-widest underline decoration-double underline-offset-4"
        >
          Parking Receipt
        </h2>

        <div class="mb-5 space-y-1">
          <div class="flex justify-between gap-2">
            <span class="shrink-0 font-bold uppercase text-[14px]">DATE:</span>
            <span class="text-right text-[16px]">{{ receiptDate }}</span>
          </div>
          <div class="flex justify-between gap-2">
            <span class="shrink-0 font-bold uppercase text-[14px]">FROM:</span>
            <span class="text-right text-[16px]">{{ receiptFrom }}</span>
          </div>
          <div class="flex justify-between gap-2">
            <span class="shrink-0 font-bold uppercase text-[14px]">TO:</span>
            <span class="text-right text-[16px]">{{ receiptTo }}</span>
          </div>
          <div class="flex justify-between gap-2 border-t border-dashed border-slate-300 pt-2">
            <span class="shrink-0 font-bold uppercase text-[14px]">PLATE:</span>
            <span class="text-right font-black text-[16px]">{{ data?.plateNumber || '-' }}</span>
          </div>
          <div class="flex justify-between gap-2">
            <span class="shrink-0 font-bold uppercase text-[14px]">METHOD:</span>
            <span class="text-right text-[16px]">{{ receiptMethod }}</span>
          </div>
        </div>

        <div class="mb-4 border-y-2 border-slate-800 py-3 text-center">
          <p class="text-[16px] font-black">Paid: ${{ data?.amount?.toFixed(2) ?? '0.00' }}</p>
        </div>

        <div class="mb-4 flex flex-col items-center gap-1 border-t border-dashed border-slate-300 pt-4">
          <p class="text-[9px] font-bold uppercase tracking-widest text-slate-500">Exit verify barcode</p>
          <USkeleton v-if="barcodeLoading" class="h-16 w-full max-w-[52mm] rounded-md" />
          <img
            v-else-if="data?.barcodeImage"
            :src="data.barcodeImage"
            alt="Exit verification barcode"
            class="h-auto w-full max-w-[52mm] object-contain"
          />
          <p v-if="data?.verifyHash" class="font-mono text-[9px] tracking-wider text-slate-600">
            {{ data.verifyHash }}
          </p>
        </div>

        <div class="space-y-1 text-center">
          <p class="text-[12px] font-bold uppercase tracking-widest">Thank you and drive safely!</p>
          <p class="text-[10px] opacity-60">System generated receipt. No signature required.</p>
        </div>
      </div>

      <div class="receipt-print-actions border-t border-default bg-muted/10 p-3 flex gap-2">
        <UButton block color="neutral" variant="soft" size="sm" @click="isOpen = false">
          Close
        </UButton>
        <UButton block color="primary" size="sm" icon="i-lucide-printer" @click="handlePrint">
          Print Receipt
        </UButton>
      </div>
    </template>
  </UModal>
</template>
