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
}>()

defineEmits<{
  (e: 'generate'): void
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
    <!-- KHQR header (no merchant name) -->
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

    <!-- Amount only -->
    <div class="bg-white px-6 pb-4 pt-5 text-center dark:bg-neutral-900">
      <p class="text-2xl font-bold tracking-tight text-neutral-900 dark:text-white sm:text-3xl">
        {{ formattedAmount }}
      </p>
    </div>

    <div class="mx-5 border-t border-dashed border-neutral-300 dark:border-neutral-600" />

    <!-- QR code -->
    <div class="flex flex-col items-center bg-white px-5 pb-6 pt-5 dark:bg-neutral-900">
      <template v-if="loading">
        <USkeleton class="aspect-square w-full max-w-[280px] rounded-lg" />
        <p class="mt-3 text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
          Generating KHQR…
        </p>
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
        <slot name="after-qr" />
      </template>

      <template v-else>
        <div class="flex aspect-square w-full max-w-[280px] flex-col items-center justify-center gap-3 rounded-lg bg-muted/20 p-4 text-center">
          <UIcon name="i-lucide-qr-code" class="size-14 text-muted-foreground opacity-40" />
          <p class="text-sm text-muted-foreground">
            {{ error || 'Scan to pay will appear when a vehicle is awaiting payment.' }}
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
