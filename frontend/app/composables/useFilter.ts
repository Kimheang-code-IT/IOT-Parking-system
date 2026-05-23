import { computed } from 'vue'
import { parseDate } from '@internationalized/date'
import { useState } from '#app'

// Global state for Date Range - persists across navigation via useState (SSR safe)
export function useGlobalFilter() {
    // Store simple strings in useState to avoid SSR serialization errors (DevalueError)
    const state = useState('globalDateRange', () => ({
        start: null as string | null,
        end: null as string | null
    }))
    
    // Transparently handle conversion between strings and CalendarDate objects for the UI
    const dateRange = computed({
        get: () => ({
            start: state.value.start ? parseDate(state.value.start) : undefined,
            end: state.value.end ? parseDate(state.value.end) : undefined
        }),
        set: (val: any) => {
            state.value = {
                start: val?.start ? val.start.toString() : null,
                end: val?.end ? val.end.toString() : null
            }
        }
    })

    const formattedRange = computed(() => {
        return { 
            start: state.value.start || '', 
            end: state.value.end || '' 
        }
    })

    const resetRange = () => {
        state.value = { start: null, end: null }
    }

    return {
        dateRange,
        formattedRange,
        resetRange
    }
}
