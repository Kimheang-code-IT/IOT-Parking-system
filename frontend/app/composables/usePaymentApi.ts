import type { ActiveVehicle, BankInfo, PaymentVerifyResult } from '~/data/payment'
import { useApiConfig } from '~/composables/useApiConfig'

export interface PaymentVerifyBody {
  plateNumber: string
  amount: number
  paymentMethod: string
  invoiceId?: string
}

export interface AbaPayStatus {
  code: string
  message: string
  traceId?: string
}

export interface AbaQrResponse {
  qrString: string
  qrImage: string
  bankLogo?: string
  logoEmbedded?: boolean
  abapayDeeplink?: string
  appStore?: string
  playStore?: string
  amount: number
  currency: string
  tranId: string
  status: AbaPayStatus
}

export function usePaymentApi() {
  const { apiUrl } = useApiConfig()

  async function getActiveSession(plate?: string, signal?: AbortSignal): Promise<ActiveVehicle> {
    return await $fetch<ActiveVehicle>(`${apiUrl.value}/api/payment/active-session`, {
      query: plate ? { plate } : undefined,
      signal
    })
  }

  async function verifyPayment(body: PaymentVerifyBody, signal?: AbortSignal): Promise<PaymentVerifyResult> {
    return await $fetch<PaymentVerifyResult>(`${apiUrl.value}/api/payment/verify`, {
      method: 'POST',
      body,
      signal
    })
  }

  async function getBankInfo(signal?: AbortSignal): Promise<BankInfo> {
    return await $fetch<BankInfo>(`${apiUrl.value}/api/payment/bank-info`, { signal })
  }

  async function getAbaQr(
    plateNumber: string,
    amount: number,
    invoiceId?: string,
    signal?: AbortSignal
  ): Promise<AbaQrResponse> {
    return await $fetch<AbaQrResponse>(`${apiUrl.value}/api/payment/aba-qr`, {
      query: {
        plateNumber,
        amount,
        ...(invoiceId ? { invoiceId } : {})
      },
      signal
    })
  }

  return { getActiveSession, verifyPayment, getBankInfo, getAbaQr }
}
