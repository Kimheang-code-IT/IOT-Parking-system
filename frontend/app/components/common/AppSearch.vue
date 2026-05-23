<script setup lang="ts">
const modelValue = defineModel<string>()

defineProps<{
  placeholder?: string
}>()
</script>

<template>
  <ClientOnly>
    <UInput 
      v-model="modelValue" 
      :placeholder="placeholder || 'Search'" 
      icon="i-lucide-search" 
      class="w-full sm:w-auto font-medium text-highlighted" 
      size="md"
      v-bind="$attrs"
      :ui="{ trailing: 'pe-1' }"
    >
      <template v-if="modelValue?.length" #trailing>
        <UButton
          color="neutral"
          variant="link"
          size="sm"
          icon="i-lucide-circle-x"
          aria-label="Clear"
          @click="modelValue = ''"
        />
      </template>
    </UInput>
  </ClientOnly>
</template>
