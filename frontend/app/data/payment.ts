/**
 * Payment page — types and API client (database via FastAPI).
 */

export interface ActiveVehicle {
  plateNumber: string
  vehicleType: string
  entryTime: string
  duration: string
  amount: number
}

export interface BankInfo {
  name: string
  accountName: string
  accountNumber: string
}

export interface PaymentVerifyResult {
  success: boolean
  message: string
  invoiceId?: string
  transactionRef?: string
}

export type { AbaQrResponse, AbaPayStatus } from '~/composables/usePaymentApi'

export async function fetchAbaQr(
  plateNumber: string,
  amount: number,
  invoiceId?: string,
  signal?: AbortSignal
) {
  return usePaymentApi().getAbaQr(plateNumber, amount, invoiceId, signal)
}

export async function fetchActiveVehicle(
  plateNumber?: string,
  signal?: AbortSignal
): Promise<ActiveVehicle> {
  return usePaymentApi().getActiveSession(plateNumber, signal)
}

export async function verifyPayment(
  plateNumber: string,
  amount: number,
  paymentMethod: string = 'ABA PAY',
  signal?: AbortSignal,
  invoiceId?: string
): Promise<PaymentVerifyResult> {
  return usePaymentApi().verifyPayment({ plateNumber, amount, paymentMethod, invoiceId }, signal)
}

export async function fetchBankInfo(signal?: AbortSignal): Promise<BankInfo> {
  return usePaymentApi().getBankInfo(signal)
}
