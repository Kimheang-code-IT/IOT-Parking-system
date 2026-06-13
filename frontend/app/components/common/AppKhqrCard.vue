<script setup lang="ts">
const props = defineProps<{
  amount: number
  currency?: string
  qrImage?: string
  bankLogo?: string
  logoEmbedded?: boolean
  loading?: boolean
  error?: string
  showGenerate?: boolean
  tranId?: string
  abapayDeeplink?: string
  checkingStatus?: boolean
  mockOnly?: boolean
}>()

defineEmits<{
  (e: 'generate'): void
  (e: 'check-status'): void
  (e: 'pay-demo'): void
}>()

const displayCurrency = computed(() => props.currency || 'USD')

const formattedAmount = computed(() => {
  const value = props.amount ?? 0
  const [whole, frac = '00'] = value.toFixed(2).split('.')
  const grouped = Number(whole).toLocaleString('en-US')
  return `${grouped},${frac} ${displayCurrency.value}`
})
</script>

<template>
  <div
    class="khqr-card mx-auto h-full w-full max-w-[min(100%,500px)] overflow-hidden rounded-xl border border-neutral-200 bg-white shadow-lg dark:border-neutral-700 dark:bg-neutral-900"
  >
    <!-- KHQR header -->
    <div class="relative bg-[#e1232e] px-6 py-5">
      <div class="flex items-center justify-center">
        <span class="select-none text-[2rem] font-black leading-none tracking-tight text-white sm:text-[2.25rem]">
          KHQ<span class="relative inline-block">R</span>
        </span>
      </div>
      <div
        class="pointer-events-none absolute bottom-0 right-0 size-10 bg-white dark:bg-neutral-900"
        style="clip-path: polygon(100% 0, 0 100%, 100% 100%)"
        aria-hidden="true"
      />
    </div>

    <div class="bg-white px-6 pb-4 pt-5 text-center dark:bg-neutral-900">
      <p class="text-2xl font-bold tracking-tight text-neutral-900 dark:text-white sm:text-3xl">
        {{ formattedAmount }}
      </p>
      <p v-if="tranId" class="mt-1 text-[10px] font-mono text-muted-foreground truncate">
        Ref: {{ tranId }}
      </p>
    </div>

    <div class="mx-5 border-t border-dashed border-neutral-300 dark:border-neutral-600" />

    <div class="flex flex-col items-center bg-white px-5 pb-6 pt-5 dark:bg-neutral-900">
      <template v-if="loading">
        <USkeleton class="aspect-square w-full max-w-[280px] rounded-lg" />
        <p class="mt-3 text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
          Generating KHQR…
        </p>
      </template>

      <template v-else-if="mockOnly && showGenerate">
        <div class="flex w-full max-w-[320px] flex-col items-center gap-4 rounded-xl border border-dashed border-warning/40 bg-warning/5 p-6 text-center">
          <UIcon name="i-lucide-wallet" class="size-14 text-warning" />
          <p class="text-sm font-semibold text-foreground">Mock payment mode</p>
          <p class="text-xs text-muted-foreground">
            Demo only — no real ABA PayWay API. Confirm payment in the dialog after ticket verification.
          </p>
          <UButton
            block
            color="primary"
            size="lg"
            icon="i-lucide-badge-check"
            :loading="checkingStatus"
            @click="$emit('pay-demo')"
          >
            Confirm mock payment
          </UButton>
        </div>
      </template>

      <template v-else-if="qrImage">
        <div class="relative aspect-square w-full max-w-[380px]">
          <img
            :src="qrImage"
            alt="KHQR payment code"
            class="size-full object-contain"
          />
          <img
            v-if="bankLogo && !logoEmbedded"
            :src="bankLogo"
            alt="ABA Bank"
            class="absolute left-1/2 top-1/2 size-[16%] min-h-8 min-w-8 max-h-14 max-w-14 -translate-x-1/2 -translate-y-1/2 rounded-full bg-white object-contain p-0.5 shadow-md ring-2 ring-white"
          />
        </div>
        <p class="mt-3 text-center text-xs text-muted-foreground">
          Scan with ABA Mobile or any KHQR-supported app
        </p>
        <slot name="after-qr" />
        <div class="mt-4 flex w-full flex-col gap-2">
          <UButton
            v-if="abapayDeeplink && !mockOnly"
            block
            color="primary"
            size="md"
            icon="i-lucide-smartphone"
            :href="abapayDeeplink"
            target="_blank"
            rel="noopener"
          >
            Open ABA Mobile
          </UButton>
          <UButton
            v-if="!mockOnly"
            block
            color="neutral"
            variant="outline"
            size="md"
            icon="i-lucide-refresh-cw"
            :loading="checkingStatus"
            @click="$emit('check-status')"
          >
            Check payment status
          </UButton>
          <UButton
            v-if="!mockOnly"
            block
            color="warning"
            variant="soft"
            size="sm"
            icon="i-lucide-badge-check"
            @click="$emit('pay-demo')"
          >
            Complete payment (demo / sandbox)
          </UButton>
        </div>
      </template>

      <template v-else>
        <div class="flex aspect-square w-full max-w-[280px] flex-col items-center justify-center gap-3 rounded-lg bg-muted/20 p-4 text-center">
          <UIcon name="i-lucide-qr-code" class="size-14 text-muted-foreground opacity-40" />
          <p class="text-sm text-muted-foreground">
            {{ error || 'Verify your ticket first, then generate the payment QR.' }}
          </p>
          <UButton
            v-if="showGenerate"
            size="xl"
            variant="outline"
            icon="i-lucide-refresh-cw"
            @click="$emit('generate')"
          >
            Generate QR
          </UButton>
        </div>
      </template>
    </div>
  </div>
</template>
