/** Normalize FastAPI / $fetch error payloads for UI messages. */
export function extractApiError(err: unknown, fallback: string): string {
  if (!err || typeof err !== 'object') return fallback
  const data = (err as { data?: unknown }).data
  if (!data || typeof data !== 'object') {
    const message = (err as { message?: string }).message
    return message || fallback
  }
  const detail = (data as { detail?: unknown; message?: string }).detail
  if (typeof detail === 'string') return detail
  if (detail && typeof detail === 'object' && 'message' in detail) {
    const msg = (detail as { message?: string }).message
    if (msg) return msg
  }
  const topMessage = (data as { message?: string }).message
  return topMessage || fallback
}
