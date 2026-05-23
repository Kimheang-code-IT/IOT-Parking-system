<script setup lang="ts">
import type { NavigationMenuItem } from '@nuxt/ui'
import { useApiConfig } from '~/composables/useApiConfig'

const open = ref(false)
const { apiUrl } = useApiConfig()

const links = [[{
  label: 'Home',
  icon: 'i-lucide-house',
  class:"text-md",
  to: '/',
  onSelect: () => {
    open.value = false
  }
}, {
  label: 'Parkings',
  icon: 'i-lucide-parking-square',
  class:"mt-2 text-md",
  to: '/parking',
  onSelect: () => {
    open.value = false
  }
},
{
  label: 'Payment',
  icon: 'i-lucide-piggy-bank',
  class:"mt-2 text-md",
  to: '/payment',
  onSelect: () => {
    open.value = false
  }
},

{
  label: 'Invoices',
  icon: 'i-lucide-receipt',
  class:"mt-2 text-md",
  to: '/invoices',
  onSelect: () => {
    open.value = false
  }
}]] satisfies NavigationMenuItem[][]

</script>

<template>
  <UDashboardGroup unit="rem">
    <UDashboardSidebar
      id="default"
      v-model:open="open"
      collapsible
      resizable
      class="bg-elevated/25 py-10"
    >
      <template #header="{ collapsed }">
        <div class="flex items-center gap-2 mx-auto pb-12">
          <img src="~/assets/image/logo.png" alt="Logo" class="h-36 w-36 object-contain" />
        </div>
      </template>

      <template #default="{ collapsed }">
        <UDashboardSearchButton :collapsed="collapsed" class="bg-transparent ring-default" />

        <UNavigationMenu
          :collapsed="collapsed"
          :items="links[0]"
          orientation="vertical"
          tooltip
          popover
        />
      </template>

      
    </UDashboardSidebar
      class="bg-elevated/25 pt-20"
    >

    <UDashboardSearch />

    <slot />
  </UDashboardGroup>
</template>
