class QueryClient {
  private cache = new Map<string, { data: any; expiry: number }>()

  async getOrFetch<T>(
    key: string,
    fetchFn: () => Promise<T>,
    ttlMs: number = 5000
  ): Promise<T> {
    const cached = this.cache.get(key)
    const now = Date.now()
    if (cached && cached.expiry > now) {
      return cached.data as T
    }

    const data = await fetchFn()
    this.cache.set(key, { data, expiry: Date.now() + ttlMs })
    return data
  }

  invalidate(resourceKey: string) {
    for (const key of this.cache.keys()) {
      if (key.startsWith(`${resourceKey}:`)) {
        this.cache.delete(key)
      }
    }
  }
}

const client = new QueryClient()

export function useQueryClient() {
  return client
}
