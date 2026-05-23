/** Full-height dashboard panel (no document scroll; content fits viewport). */
export const TABLE_PANEL_UI = {
  root: 'relative flex flex-col min-w-0 min-h-0 h-full flex-1 overflow-hidden',
  body: 'flex flex-col flex-1 min-h-0 overflow-hidden p-3 gap-0'
} as const

export const TABLE_PAGE_BODY_CLASS =
  'flex flex-col flex-1 min-h-0 h-full overflow-hidden -m-4'

/** Payment page body — same height contract as table pages */
export const PAYMENT_PAGE_BODY_CLASS = TABLE_PAGE_BODY_CLASS
