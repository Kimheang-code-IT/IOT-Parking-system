/** Receipt line formats (matches printed ticket layout). */

function parseWhen(value: string | Date | number | undefined | null): Date | null {
  if (value === undefined || value === null || value === '') return null
  if (value instanceof Date) return isNaN(value.getTime()) ? null : value
  const d = new Date(value)
  if (!isNaN(d.getTime())) return d
  const m = String(value).match(/^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?/)
  if (m) {
    const [, y, mo, day, h = '0', min = '0', sec = '0'] = m
    return new Date(Number(y), Number(mo) - 1, Number(day), Number(h), Number(min), Number(sec))
  }
  return null
}

/** DATE: 5/23/2026 */
export function formatReceiptDate(value: string | Date | number | undefined | null): string {
  const d = parseWhen(value) ?? new Date()
  return new Intl.DateTimeFormat('en-US', {
    month: 'numeric',
    day: 'numeric',
    year: 'numeric'
  }).format(d)
}

/** FROM: 2026-05-22 8:59 PM */
export function formatReceiptFrom(value: string | Date | number | undefined | null): string {
  const d = parseWhen(value)
  if (!d) return value ? String(value) : '-'
  const parts = new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true
  }).formatToParts(d)
  const get = (type: Intl.DateTimeFormatPartTypes) => parts.find((p) => p.type === type)?.value ?? ''
  return `${get('year')}-${get('month')}-${get('day')} ${get('hour')}:${get('minute')} ${get('dayPeriod')}`
}

/** TO: 5/23/2026, 10:42:27 AM */
export function formatReceiptTo(value: string | Date | number | undefined | null): string {
  const d = parseWhen(value) ?? new Date()
  return new Intl.DateTimeFormat('en-US', {
    month: 'numeric',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit',
    hour12: true
  }).format(d)
}
