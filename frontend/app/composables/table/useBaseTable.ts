import { ref } from 'vue'
import type { RowSelectionState, VisibilityState } from '@tanstack/vue-table'
import { useI18n } from 'vue-i18n'
import { useToast } from '@nuxt/ui/composables'

export interface BaseTableOptions {
  initialVisibility?: VisibilityState
}

export function useBaseTable(options: BaseTableOptions = {}) {
  const { t } = useI18n()
  const toast = useToast()

  // --- UI-Specific Table States ---
  // Purely visual or interaction states (not sent to API endpoints)
  const rowSelection = ref<RowSelectionState>({})
  const columnVisibility = ref<VisibilityState>(options.initialVisibility || {})

  // --- Common Sidebar/Overlay States ---
  const isAnalyticsOpen = ref(false)
  const isFormOpen = ref(false)
  const isDetailOpen = ref(false)
  const isConfirmOpen = ref(false)

  /**
   * Resets table UI states like selection
   */
  function resetUiState() {
    rowSelection.value = {}
  }

  return {
    t,
    toast,
    // TanStack UI States
    rowSelection,
    columnVisibility,
    // Overlay States
    isAnalyticsOpen,
    isFormOpen,
    isDetailOpen,
    isConfirmOpen,
    // Methods
    resetUiState
  }
}
