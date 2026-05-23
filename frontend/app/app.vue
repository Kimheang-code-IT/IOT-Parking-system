<script setup lang="ts">
const colorMode = useColorMode()
const config = useRuntimeConfig()

const siteName = 'IOT Parking System'
const description =
  'Smart parking management dashboard — vehicle entry and exit, barcode verification, KHQR payments, invoices, and real-time occupancy.'

const color = computed(() => (colorMode.value === 'dark' ? '#1b1718' : '#ffffff'))

const siteUrl = computed(() => {
  const base = config.public.siteUrl || 'http://localhost:3000'
  return String(base).replace(/\/$/, '')
})

const ogImage = computed(() => `${siteUrl.value}/favicon.png`)

useHead({
  titleTemplate: (titleChunk) => (titleChunk ? `${titleChunk} · ${siteName}` : siteName),
  meta: [
    { charset: 'utf-8' },
    { name: 'viewport', content: 'width=device-width, initial-scale=1' },
    { key: 'theme-color', name: 'theme-color', content: color },
    { name: 'author', content: siteName },
    { name: 'format-detection', content: 'telephone=no' }
  ],
  link: [
    { rel: 'icon', type: 'image/png', href: '/favicon.png' },
    { rel: 'apple-touch-icon', href: '/apple-touch-icon.png' }
  ],
  htmlAttrs: {
    lang: 'en'
  }
})

useSeoMeta({
  title: siteName,
  description,
  applicationName: siteName,
  keywords:
    'IOT parking, smart parking, parking management, KHQR, ABA pay, parking invoice, vehicle entry, exit verification',
  robots: 'index, follow',
  ogTitle: siteName,
  ogDescription: description,
  ogType: 'website',
  ogSiteName: siteName,
  ogImage,
  ogUrl: siteUrl,
  ogLocale: 'en_US',
  twitterCard: 'summary',
  twitterTitle: siteName,
  twitterDescription: description,
  twitterImage: ogImage
})
</script>

<template>
  <UApp>
    <NuxtLoadingIndicator />

    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
  </UApp>
</template>
