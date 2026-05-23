/**
 * Strip empty values and keep array params for FastAPI list[...] query parsing.
 */
export function toListQuery(query: Record<string, unknown>): Record<string, string | number | string[]> {
  const out: Record<string, string | number | string[]> = {}

  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '') {
      continue
    }
    if (Array.isArray(value)) {
      if (value.length > 0) {
        out[key] = value.map(String)
      }
      continue
    }
    out[key] = value as string | number
  }

  return out
}
