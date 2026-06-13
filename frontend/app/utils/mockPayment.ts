import type { AbaQrResponse } from '~/composables/usePaymentApi'

/** Local mock KHQR payload — no real PayWay API. */
export function buildMockAbaQr(plateNumber: string, amount: number, invoiceId?: string): AbaQrResponse {
  const tranId = `MOCK-${Date.now().toString(36).toUpperCase()}`
  const qrString = `MOCK-KHQR|${plateNumber}|${amount.toFixed(2)}|${invoiceId || tranId}`
  return {
    qrString,
    qrImage: '',
    amount: roundAmount(amount),
    currency: 'USD',
    tranId,
    logoEmbedded: false,
    status: {
      code: '0',
      message: 'Mock payment (demo only — no real ABA API).'
    }
  }
}

function roundAmount(value: number) {
  return Math.round(value * 100) / 100
}
