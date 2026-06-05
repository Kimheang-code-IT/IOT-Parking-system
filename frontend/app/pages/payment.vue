<script setup lang="ts">
import { useParkingLiveSync } from '~/composables/useParkingLiveSync'
import { fetchActiveVehicle, fetchAbaQr, fetchBankInfo, verifyPayment } from '~/data/payment'
import type { AbaQrResponse } from '~/data/payment'
import { TABLE_PANEL_UI, PAYMENT_PAGE_BODY_CLASS } from '~/utils/tablePanelLayout'
import CommonAppKhqrCard from '~/components/common/AppKhqrCard.vue'
import abaLogoSecondary from '~/assets/image/ABA-Logo-Secondary.png.webp'

const amount = ref(0)
const plateNumber = ref('—')
const vehicleType = ref('—')
const entryTime = ref('—')
const duration = ref('—')
const bankInfo = reactive({ name: '', accountName: '', accountNumber: '' })
const loading = ref(false)
const hasActiveSession = ref(false)
const loadError = ref('')
const qrLoading = ref(false)
const qrError = ref('')
const abaQr = ref<AbaQrResponse | null>(null)
const invoiceId = ref<string | undefined>(undefined)
const payConfirmLoading = ref(false)

async function loadActiveVehicle() {
  loading.value = true
  loadError.value = ''
  hasActiveSession.value = false
  try {
    const vehicle = await fetchActiveVehicle(undefined)
    plateNumber.value = vehicle.plateNumber
    vehicleType.value = vehicle.vehicleType
    entryTime.value = vehicle.entryTime
    duration.value = vehicle.duration
    amount.value = vehicle.amount
    invoiceId.value = vehicle.invoiceId
    hasActiveSession.value = true
    await loadAbaQr()
  } catch {
    plateNumber.value = '—'
    vehicleType.value = '—'
    entryTime.value = '—'
    duration.value = '—'
    amount.value = 0
    invoiceId.value = undefined
    loadError.value = 'No vehicle awaiting payment. Scan exit barcode at the gate or wait for an active session.'
    abaQr.value = null
  } finally {
    loading.value = false
  }
}

async function confirmSandboxPayment() {
  if (!hasActiveSession.value || amount.value <= 0) return
  payConfirmLoading.value = true
  try {
    await verifyPayment(plateNumber.value, amount.value, 'ABA PAY', undefined, invoiceId.value)
    await loadActiveVehicle()
  } catch (err: any) {
    qrError.value = err?.data?.message || err?.message || 'Payment confirmation failed.'
  } finally {
    payConfirmLoading.value = false
  }
}

async function loadAbaQr() {
  if (!hasActiveSession.value || amount.value <= 0) {
    abaQr.value = null
    return
  }
  qrLoading.value = true
  qrError.value = ''
  try {
    abaQr.value = await fetchAbaQr(plateNumber.value, amount.value, invoiceId.value)
  } catch (err: any) {
    abaQr.value = null
    qrError.value = err?.data?.message || err?.message || 'Failed to generate ABA payment QR.'
  } finally {
    qrLoading.value = false
  }
}

async function loadBankInfo() {
  try {
    const info = await fetchBankInfo()
    Object.assign(bankInfo, info)
  } catch (err) {
    console.error('Failed to load bank info:', err)
  }
}

onMounted(() => {
  loadActiveVehicle()
  loadBankInfo()
})

useParkingLiveSync(loadActiveVehicle)
</script>

<template>
  <UDashboardPanel id="payment" :ui="TABLE_PANEL_UI">
    <template #header>
      <UDashboardNavbar title="Parking Payment">
        <template #leading>
          <UDashboardSidebarCollapse />
        </template>
        <template #right>
          <div class="flex items-center gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              icon="i-lucide-refresh-cw"
              size="xs"
              class="font-bold"
              :loading="loading"
              @click="loadActiveVehicle"
            >
              Refresh
            </UButton>
            <UBadge v-if="hasActiveSession" color="warning" variant="subtle" size="sm">Pending Payment</UBadge>
            <UBadge v-else color="neutral" variant="subtle" size="sm">No active session</UBadge>
          </div>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div :class="[PAYMENT_PAGE_BODY_CLASS, 'bg-muted/5']">
        <UAlert
          v-if="loadError && !loading"
          class="shrink-0 mb-3"
          color="neutral"
          variant="subtle"
          :title="loadError"
        />

        <div
          class="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-2 gap-4 lg:gap-6 overflow-hidden w-full mx-auto"
        >
          <!-- Vehicle details -->
          <div class="flex flex-col min-h-0 gap-3 overflow-y-auto">
            <template v-if="loading">
              <div class="grid grid-cols-1 gap-3 shrink-0">
                <USkeleton class="h-24 w-full rounded-lg" />
                <div class="grid grid-cols-2 gap-3">
                  <USkeleton class="h-16 w-full rounded-lg" />
                  <USkeleton class="h-16 w-full rounded-lg" />
                </div>
                <USkeleton class="h-14 w-full rounded-lg" />
              </div>
            </template>
            <template v-else>
              <div class="grid grid-cols-1 gap-3 shrink-0">
                <div class="p-4 sm:p-5 rounded-lg bg-muted/30 border border-default shadow-sm">
                  <p class="text-[10px] uppercase tracking-widest font-bold text-muted-foreground mb-1">
                    License Plate
                  </p>
                  <p class="text-3xl sm:text-4xl font-black tracking-tighter text-error truncate">
                    {{ plateNumber }}
                  </p>
                </div>

                <div class="grid grid-cols-2 gap-3">
                  <div class="p-3 sm:p-4 rounded-lg border border-default bg-background/50 min-w-0">
                    <p class="text-[10px] uppercase tracking-widest font-bold text-muted-foreground mb-1">
                      Vehicle Type
                    </p>
                    <p class="font-bold text-sm sm:text-base text-primary truncate">{{ vehicleType }}</p>
                  </div>
                  <div class="p-3 sm:p-4 rounded-lg border border-default bg-background/50 min-w-0">
                    <p class="text-[10px] uppercase tracking-widest font-bold text-muted-foreground mb-1">
                      Entry Time
                    </p>
                    <p class="font-bold text-sm sm:text-base text-primary truncate">{{ entryTime }}</p>
                  </div>
                </div>

                <div
                  class="p-3 sm:p-4 rounded-lg border border-default bg-background/50 flex items-center justify-between gap-2"
                >
                  <div class="min-w-0">
                    <p class="text-[10px] uppercase tracking-widest font-bold text-muted-foreground mb-1">
                      Parking Duration
                    </p>
                    <p class="font-bold text-sm sm:text-base text-primary truncate">{{ duration }}</p>
                  </div>
                  <div class="p-2 bg-muted/20 rounded-lg shrink-0">
                    <UIcon name="i-lucide-clock" class="size-5 sm:size-6 text-muted-foreground" />
                  </div>
                </div>
              </div>
            </template>

            <USeparator class="shrink-0" />

            <div class="flex items-end justify-between gap-3 px-1 shrink-0 pb-1">
              <div class="min-w-0">
                <p class="text-xs font-bold text-muted-foreground uppercase tracking-widest">Total Fee Due</p>
                <p class="text-4xl sm:text-5xl font-black text-primary tracking-tighter pt-2 sm:pt-3">
                  ${{ amount.toFixed(2) }}
                </p>
              </div>
              <UBadge variant="soft" color="neutral" size="lg" class="font-bold italic shrink-0 hidden sm:inline-flex">
                Rate: $2.00 / Hour
              </UBadge>
            </div>
            <UBadge variant="soft" color="neutral" size="sm" class="font-bold italic shrink-0 sm:hidden w-fit">
              Rate: $2.00 / Hour
            </UBadge>
            <UButton
              v-if="hasActiveSession && amount > 0"
              class="shrink-0 w-fit"
              color="primary"
              variant="soft"
              size="sm"
              :loading="payConfirmLoading"
              @click="confirmSandboxPayment"
            >
              Confirm payment (sandbox)
            </UButton>
          </div>

          <!-- KHQR-style payment card -->
          <div class="flex flex-1 min-h-[200px] lg:min-h-0 flex-col items-center justify-center overflow-hidden p-2 sm:p-4">
            <CommonAppKhqrCard
              :amount="abaQr?.amount ?? amount"
              :currency="abaQr?.currency"
              :qr-image="abaQr?.qrImage"
              :bank-logo="abaQr?.bankLogo"
              :logo-embedded="abaQr?.logoEmbedded"
              :loading="qrLoading"
              :error="qrError"
              :show-generate="hasActiveSession"
              @generate="loadAbaQr"
            >
              <template v-if="abaQr?.qrImage" #after-qr>
                <img
                  :src="abaLogoSecondary"
                  alt="ABA Bank"
                  class="mt-4 w-auto max-w-[200px] object-contain"
                />
              </template>
            </CommonAppKhqrCard>
          </div>
        </div>
      </div>
    </template>

    <template #footer>
      <div class="shrink-0 flex items-center justify-between text-[10px] text-muted-foreground uppercase font-black tracking-[0.2em] w-full px-4 py-3 border-t border-default">
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-shield-check" class="size-4 text-green-500" />
          <span>Secure Encrypted Transaction</span>
        </div>
        <div v-if="bankInfo.name" class="flex items-center gap-2 opacity-70 truncate">
          <span>{{ bankInfo.name }} · {{ bankInfo.accountNumber }}</span>
        </div>
      </div>
    </template>
  </UDashboardPanel>
</template>
