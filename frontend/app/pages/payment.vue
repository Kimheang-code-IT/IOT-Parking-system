<script setup lang="ts">
import { useParkingLiveSync } from '~/composables/useParkingLiveSync'
import { fetchActiveVehicle, fetchBankInfo, fetchPaymentConfig, fetchPaymentStatus, verifyPayment } from '~/data/payment'
import type { AbaQrResponse } from '~/data/payment'
import { TABLE_PANEL_UI, PAYMENT_PAGE_BODY_CLASS } from '~/utils/tablePanelLayout'
import { extractApiError } from '~/utils/extractApiError'
import { buildMockAbaQr } from '~/utils/mockPayment'
import CommonAppKhqrCard from '~/components/common/AppKhqrCard.vue'
import abaLogoSecondary from '~/assets/image/ABA-Logo-Secondary.png.webp'

const amount = ref(0)
const plateNumber = ref('—')
const plateInput = ref('')
const verifyHashInput = ref('')
const vehicleType = ref('—')
const entryTime = ref('—')
const duration = ref('—')
const bankInfo = reactive({ name: '', accountName: '', accountNumber: '' })
const loading = ref(false)
const hasActiveSession = ref(false)
const ticketVerified = ref(false)
const loadError = ref('')
const qrLoading = ref(false)
const qrError = ref('')
const abaQr = ref<AbaQrResponse | null>(null)
const invoiceId = ref<string | undefined>(undefined)
const payConfirmLoading = ref(false)
const paymentComplete = ref(false)
const successMessage = ref('')
const transactionRef = ref('')
const statusChecking = ref(false)
const mockOnly = ref(true)
const showConfirmDialog = ref(false)

let pollTimer: ReturnType<typeof setInterval> | null = null

const BARCODE_PREFIX = 'IOT-PARKING:'
const VERIFY_CODE_LENGTH = 4

function normalizeVerifyCode(raw: string) {
  return raw.trim().toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, VERIFY_CODE_LENGTH)
}

function parseExitBarcode(raw: string): { plate: string; verifyHash: string } | null {
  const text = raw.trim()
  if (!text.toUpperCase().startsWith(BARCODE_PREFIX)) return null
  const parts = text.slice(BARCODE_PREFIX.length).split('|').map((p) => p.trim())
  if (parts.length !== 3 || !parts[0] || !parts[2]) return null
  return { plate: parts[0], verifyHash: normalizeVerifyCode(parts[2]) }
}

function onVerifyCodeInput(raw: string) {
  const parsed = parseExitBarcode(raw)
  if (parsed) {
    plateInput.value = parsed.plate
    verifyHashInput.value = parsed.verifyHash
    return
  }
  verifyHashInput.value = normalizeVerifyCode(raw)
}

function applyMockPaymentPreview() {
  abaQr.value = buildMockAbaQr(plateNumber.value, amount.value, invoiceId.value)
}

function openConfirmDialog() {
  if (hasActiveSession.value && ticketVerified.value && amount.value > 0) {
    showConfirmDialog.value = true
  }
}

function closeConfirmDialog() {
  showConfirmDialog.value = false
}

async function executeMockPayment() {
  await confirmSandboxPayment()
  if (paymentComplete.value) {
    closeConfirmDialog()
  }
}

function stopPaymentPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function startPaymentPolling() {
  stopPaymentPolling()
  if (!invoiceId.value || paymentComplete.value) return
  pollTimer = setInterval(() => void checkPaymentStatus(true), 4000)
}

function onPaymentSuccess(message: string, ref?: string) {
  paymentComplete.value = true
  hasActiveSession.value = false
  ticketVerified.value = false
  successMessage.value = message
  transactionRef.value = ref || ''
  abaQr.value = null
  stopPaymentPolling()
}

function resetForNewPayment() {
  paymentComplete.value = false
  successMessage.value = ''
  transactionRef.value = ''
  loadError.value = ''
  qrError.value = ''
  resetSessionDisplay()
  plateInput.value = ''
  verifyHashInput.value = ''
  stopPaymentPolling()
}

function resetSessionDisplay() {
  plateNumber.value = '—'
  vehicleType.value = '—'
  entryTime.value = '—'
  duration.value = '—'
  amount.value = 0
  invoiceId.value = undefined
  hasActiveSession.value = false
  ticketVerified.value = false
  abaQr.value = null
}

async function loadActiveVehicle() {
  if (paymentComplete.value) return

  const plate = plateInput.value.trim()
  const verifyHash = normalizeVerifyCode(verifyHashInput.value)
  verifyHashInput.value = verifyHash
  if (!plate) {
    loadError.value = 'Enter a license plate from the entry ticket.'
    resetSessionDisplay()
    return
  }
  if (!verifyHash) {
    loadError.value = 'Enter the 4-character verify code from the entry ticket.'
    resetSessionDisplay()
    return
  }
  if (verifyHash.length !== VERIFY_CODE_LENGTH) {
    loadError.value = `Ticket verify code must be exactly ${VERIFY_CODE_LENGTH} characters.`
    resetSessionDisplay()
    return
  }

  loading.value = true
  loadError.value = ''
  hasActiveSession.value = false
  ticketVerified.value = false
  try {
    const vehicle = await fetchActiveVehicle(plate, verifyHash)
    plateNumber.value = vehicle.plateNumber
    plateInput.value = vehicle.plateNumber
    vehicleType.value = vehicle.vehicleType
    entryTime.value = vehicle.entryTime
    duration.value = vehicle.duration
    amount.value = vehicle.amount
    invoiceId.value = vehicle.invoiceId
    hasActiveSession.value = true
    ticketVerified.value = true
    if (vehicle.paymentStatus?.toLowerCase() === 'paid') {
      onPaymentSuccess('Payment already completed. Proceed to the exit gate.')
      return
    }
    if (mockOnly.value) {
      applyMockPaymentPreview()
      openConfirmDialog()
    } else {
      await loadAbaQr()
      startPaymentPolling()
    }
  } catch (err: unknown) {
    resetSessionDisplay()
    loadError.value = extractApiError(err, 'No matching session. Check plate and verify code from the entry ticket.')
  } finally {
    loading.value = false
  }
}

async function checkPaymentStatus(silent = false) {
  if (paymentComplete.value || !invoiceId.value || !ticketVerified.value) return
  if (!silent) statusChecking.value = true
  try {
    const status = await fetchPaymentStatus(
      invoiceId.value,
      normalizeVerifyCode(verifyHashInput.value)
    )
    if (status.paid) {
      onPaymentSuccess('Payment received. Customer may proceed to the exit gate.')
    }
  } catch (err: unknown) {
    if (!silent) qrError.value = extractApiError(err, 'Could not check payment status.')
  } finally {
    if (!silent) statusChecking.value = false
  }
}

async function confirmSandboxPayment() {
  if (!hasActiveSession.value || !ticketVerified.value || amount.value <= 0) return
  payConfirmLoading.value = true
  qrError.value = ''
  try {
    const result = await verifyPayment(
      plateNumber.value,
      amount.value,
      'ABA PAY',
      undefined,
      invoiceId.value,
      normalizeVerifyCode(verifyHashInput.value)
    )
    if (result.success) {
      onPaymentSuccess(
        result.message || 'Payment verified. Customer may proceed to the exit gate.',
        result.transactionRef
      )
    } else {
      qrError.value = result.message || 'Payment confirmation failed.'
    }
  } catch (err: unknown) {
    qrError.value = extractApiError(err, 'Payment confirmation failed.')
  } finally {
    payConfirmLoading.value = false
  }
}

async function loadAbaQr() {
  if (!hasActiveSession.value || amount.value <= 0) {
    abaQr.value = null
    return
  }
  if (mockOnly.value) {
    applyMockPaymentPreview()
    return
  }
  qrLoading.value = true
  qrError.value = ''
  try {
    const { fetchAbaQr } = await import('~/data/payment')
    abaQr.value = await fetchAbaQr(plateNumber.value, amount.value, invoiceId.value)
  } catch (err: unknown) {
    abaQr.value = null
    qrError.value = extractApiError(err, 'Failed to generate ABA payment QR.')
  } finally {
    qrLoading.value = false
  }
}

async function loadPaymentConfig() {
  try {
    const config = await fetchPaymentConfig()
    mockOnly.value = config.mockOnly
  } catch {
    mockOnly.value = true
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
  loadBankInfo()
  loadPaymentConfig()
})

onBeforeUnmount(() => {
  stopPaymentPolling()
})

useParkingLiveSync(() => {
  if (hasActiveSession.value && !paymentComplete.value && !mockOnly.value) {
    void checkPaymentStatus(true)
  }
})
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
              :disabled="!plateInput.trim() || verifyHashInput.length !== VERIFY_CODE_LENGTH"
              @click="loadActiveVehicle"
            >
              Refresh
            </UButton>
            <UBadge v-if="hasActiveSession && ticketVerified" color="success" variant="subtle" size="sm">
              Ticket verified
            </UBadge>
            <UBadge v-else-if="hasActiveSession" color="warning" variant="subtle" size="sm">Pending Payment</UBadge>
            <UBadge v-else color="neutral" variant="subtle" size="sm">No active session</UBadge>
          </div>
        </template>
      </UDashboardNavbar>
    </template>

    <template #body>
      <div :class="[PAYMENT_PAGE_BODY_CLASS, 'bg-muted/5']">
        <div v-if="successMessage" class="shrink-0 mb-3 space-y-2">
          <UAlert
            color="success"
            variant="subtle"
            :title="successMessage"
            :description="transactionRef ? `Transaction ref: ${transactionRef}` : 'Proceed to the exit gate with your ticket.'"
          />
          <UButton color="success" variant="soft" size="sm" @click="resetForNewPayment">
            New payment
          </UButton>
        </div>
        <UAlert
          v-if="loadError && !loading && !paymentComplete"
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
                <div class="p-4 sm:p-5 rounded-lg bg-muted/30 border border-default shadow-sm space-y-3">
                  <div>
                    <p class="text-[10px] uppercase tracking-widest font-bold text-muted-foreground mb-1">
                      License Plate
                    </p>
                    <UInput
                      v-model="plateInput"
                      placeholder="e.g. 2A-1234"
                      size="xl"
                      class="w-full font-black tracking-tighter"
                      :ui="{ base: 'text-error text-2xl sm:text-3xl uppercase' }"
                      @keyup.enter="loadActiveVehicle"
                    />
                  </div>
                  <div>
                    <p class="text-[10px] uppercase tracking-widest font-bold text-muted-foreground mb-1">
                      Ticket Verify Code
                    </p>
                    <UInput
                      v-model="verifyHashInput"
                      placeholder="4-character code"
                      size="md"
                      maxlength="4"
                      class="w-full max-w-[8rem] font-mono uppercase tracking-[0.35em] text-center"
                      :ui="{ base: 'text-lg font-bold' }"
                      @update:model-value="onVerifyCodeInput"
                      @keyup.enter="loadActiveVehicle"
                    />
                  </div>
                  <UButton
                    block
                    color="primary"
                    icon="i-lucide-search"
                    :loading="loading"
                    :disabled="!plateInput.trim() || verifyHashInput.length !== VERIFY_CODE_LENGTH"
                    @click="loadActiveVehicle"
                  >
                    Look up & verify ticket
                  </UButton>
                  <p
                    v-if="hasActiveSession && ticketVerified"
                    class="text-center text-2xl sm:text-3xl font-black tracking-tighter text-error truncate"
                  >
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

            <div
              v-if="hasActiveSession && ticketVerified && !paymentComplete"
              class="rounded-lg border border-primary/20 bg-primary/5 p-3 space-y-2 shrink-0"
            >
              <p class="text-xs font-bold uppercase tracking-widest text-primary">Pay to exit</p>
              <p class="text-sm text-muted-foreground">
                {{ mockOnly ? 'Confirm mock payment in the dialog — demo only, no real ABA API.' : 'Scan the KHQR on the right with ABA Mobile.' }}
              </p>
              <div v-if="invoiceId" class="text-[10px] font-mono text-muted-foreground truncate">
                Invoice: {{ invoiceId }}
              </div>
            </div>
          </div>

          <!-- KHQR-style payment card -->
          <div class="flex flex-1 min-h-[200px] lg:min-h-0 flex-col items-center justify-center overflow-hidden p-2 sm:p-4">
            <CommonAppKhqrCard
              :amount="abaQr?.amount ?? amount"
              :currency="abaQr?.currency"
              :qr-image="abaQr?.qrImage"
              :bank-logo="abaQr?.bankLogo"
              :logo-embedded="abaQr?.logoEmbedded"
              :tran-id="abaQr?.tranId"
              :abapay-deeplink="mockOnly ? undefined : abaQr?.abapayDeeplink"
              :mock-only="mockOnly"
              :loading="qrLoading"
              :error="qrError"
              :checking-status="statusChecking || payConfirmLoading"
              :show-generate="hasActiveSession && ticketVerified && !paymentComplete"
              @generate="loadAbaQr"
              @check-status="checkPaymentStatus(false)"
              @pay-demo="openConfirmDialog"
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

  <UModal v-model:open="showConfirmDialog" :dismissible="!payConfirmLoading">
    <template #content>
      <div class="p-6 space-y-4">
        <div class="flex items-start gap-3">
          <div class="rounded-full bg-primary/10 p-2">
            <UIcon name="i-lucide-wallet" class="size-6 text-primary" />
          </div>
          <div>
            <h3 class="text-lg font-bold">Confirm mock payment</h3>
            <p class="text-sm text-muted-foreground mt-1">
              Demo only — no real ABA PayWay API. This marks the invoice as paid in the local database.
            </p>
          </div>
        </div>

        <div class="rounded-lg border border-default bg-muted/20 p-4 space-y-2 text-sm">
          <div class="flex justify-between gap-2">
            <span class="text-muted-foreground">Plate</span>
            <span class="font-bold uppercase">{{ plateNumber }}</span>
          </div>
          <div class="flex justify-between gap-2">
            <span class="text-muted-foreground">Verify code</span>
            <span class="font-mono font-bold">{{ verifyHashInput }}</span>
          </div>
          <div class="flex justify-between gap-2">
            <span class="text-muted-foreground">Invoice</span>
            <span class="font-mono text-xs truncate max-w-[12rem]">{{ invoiceId || '—' }}</span>
          </div>
          <div class="flex justify-between gap-2 border-t border-default pt-2">
            <span class="text-muted-foreground">Amount due</span>
            <span class="text-xl font-black text-primary">${{ amount.toFixed(2) }}</span>
          </div>
        </div>

        <div class="flex justify-end gap-2">
          <UButton color="neutral" variant="ghost" :disabled="payConfirmLoading" @click="closeConfirmDialog">
            Cancel
          </UButton>
          <UButton
            color="primary"
            icon="i-lucide-check"
            :loading="payConfirmLoading"
            @click="executeMockPayment"
          >
            Confirm payment
          </UButton>
        </div>
      </div>
    </template>
  </UModal>
</template>
