/**
 * Payment page — types and API client (database via FastAPI).
 */

export interface ActiveVehicle {
  plateNumber: string
  vehicleType: string
  entryTime: string
  duration: string
  amount: number
  invoiceId?: string
  sessionId?: string
  paymentStatus?: string
  verifyHash?: string
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

export interface PaymentStatus {
  paid: boolean
  paymentStatus: string
  plateNumber: string
  amount: number
  invoiceId: string
  canExit: boolean
}

export interface PaymentConfig {
  mockOnly: boolean
  useAbaMock: boolean
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
  verifyHash?: string,
  signal?: AbortSignal
): Promise<ActiveVehicle> {
  return usePaymentApi().getActiveSession(plateNumber, verifyHash, signal)
}

export async function verifyPayment(
  plateNumber: string,
  amount: number,
  paymentMethod: string = 'ABA PAY',
  signal?: AbortSignal,
  invoiceId?: string,
  verifyHash?: string
): Promise<PaymentVerifyResult> {
  return usePaymentApi().verifyPayment({ plateNumber, amount, paymentMethod, invoiceId, verifyHash }, signal)
}

export async function fetchBankInfo(signal?: AbortSignal): Promise<BankInfo> {
  return usePaymentApi().getBankInfo(signal)
}

export async function fetchPaymentConfig(signal?: AbortSignal): Promise<PaymentConfig> {
  return usePaymentApi().getPaymentConfig(signal)
}

export async function fetchPaymentStatus(
  invoiceId: string,
  verifyHash: string,
  signal?: AbortSignal
): Promise<PaymentStatus> {
  return usePaymentApi().getPaymentStatus(invoiceId, verifyHash, signal)
}
