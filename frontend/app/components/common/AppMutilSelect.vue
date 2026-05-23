<script setup lang="ts">
export interface FilterItem {
  label: string
  value: string
  icon?: string
  color?: string
}

const modelValue = defineModel<string[]>({ default: () => [] })

const props = defineProps<{
  items: FilterItem[]
  placeholder?: string
}>()

const displayLabel = computed(() => {
  if (!modelValue.value?.length) {
    return props.placeholder || 'Filter'
  }
  const labels = modelValue.value
    .map((v) => props.items.find((item) => item.value === v)?.label ?? v)
    .filter(Boolean)
  return labels.length <= 2 ? labels.join(', ') : `${labels.length} selected`
})
</script>

<template>
  <USelectMenu
    v-model="modelValue"
    multiple
    :items="items"
    value-key="value"
    :placeholder="displayLabel"
    size="md"
    class="w-40 min-w-40 font-medium"
    :ui="{ trailing: 'pe-1' }"
  >
    <template v-if="modelValue?.length" #trailing>
      <UButton
        color="neutral"
        variant="link"
        size="sm"
        icon="i-lucide-circle-x"
        aria-label="Clear filter"
        @click.stop="modelValue = []"
      />
    </template>
  </USelectMenu>
</template>
