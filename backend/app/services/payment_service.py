from decimal import Decimal

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.bank_settings import BankSettings
from app.models.invoice import Invoice
from app.models.parking_session import ParkingSession
from app.schemas.payment import ActiveSessionOut, BankInfoOut, PaymentVerifyOut, PaymentWebhookIn
from app.services.invoice_service import InvoiceService
from app.services.parking_service import ParkingService
from app.services.plate_service import normalize_plate
from app.utils.datetime_utils import utc_now
from app.utils.id_generator import next_transaction_ref
from app.models.payment_transaction import PaymentTransaction


class PaymentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.parking_service = ParkingService(db)
        self.invoice_service = InvoiceService(db)

    def get_active_session(self, plate: str | None) -> ActiveSessionOut | None:
        if not plate:
            session = (
                self.db.query(ParkingSession)
                .filter(ParkingSession.status == "Active")
                .order_by(desc(ParkingSession.entry_time))
                .first()
            )
            if not session:
                return None
            plate = session.license_plate
        data = self.parking_service.active_session_card(plate)
        if not data:
            return None
        return ActiveSessionOut.model_validate(data)

    def get_bank_info(self) -> BankInfoOut:
        row = self.db.query(BankSettings).first()
        if not row:
            return BankInfoOut(name="ABA Bank", account_name="Parking System", account_number="001234567")
        return BankInfoOut(name=row.name, account_name=row.account_name, account_number=row.account_number)

    def verify_payment(
        self,
        plate_number: str,
        amount: float,
        payment_method: str,
        invoice_id: str | None,
    ) -> PaymentVerifyOut:
        plate = normalize_plate(plate_number)
        session = self.parking_service.get_active_by_plate(plate)
        if not session:
            return PaymentVerifyOut(success=False, message="No active parking session for this plate.")

        invoice: Invoice | None = None
        if invoice_id:
            invoice = self.invoice_service.get_by_id(invoice_id)
        else:
            invoice = (
                self.db.query(Invoice)
                .filter(Invoice.session_id == session.id, Invoice.status == "Pending")
                .order_by(Invoice.created_at.desc())
                .first()
            )

        if not invoice:
            return PaymentVerifyOut(success=False, message="Pending invoice not found.")

        if session.fee_amount is not None:
            expected = float(session.fee_amount)
        elif invoice.amount:
            expected = float(invoice.amount)
        else:
            from app.services.parking_fee_service import ParkingFeeService
            from app.utils.datetime_utils import duration_between

            total_minutes, _, _ = duration_between(session.entry_time, utc_now())
            expected = float(ParkingFeeService().calculate_fee(total_minutes))

        if round(expected, 2) != round(amount, 2):
            return PaymentVerifyOut(
                success=False,
                message=f"Amount mismatch. Expected ${expected:.2f}, received ${amount:.2f}.",
            )

        if not self._simulate_gateway_success(payment_method, amount):
            tx_ref = next_transaction_ref(self.db)
            self._save_transaction(session.id, plate, amount, payment_method, False, "Payment declined.", tx_ref)
            self.db.commit()
            return PaymentVerifyOut(success=False, message="Payment declined by gateway.")

        tx_ref = next_transaction_ref(self.db)
        self.parking_service.close_session(session)
        invoice.amount = Decimal(str(amount))
        self.invoice_service.mark_paid(invoice, payment_method, tx_ref)
        self._save_transaction(session.id, plate, amount, payment_method, True, "Payment verified successfully.", tx_ref)
        self.db.commit()

        return PaymentVerifyOut(
            success=True,
            message="Payment verified successfully.",
            invoice_id=invoice.id,
            transaction_ref=tx_ref,
        )

    def _save_transaction(
        self,
        session_id: str,
        plate: str,
        amount: float,
        payment_method: str,
        success: bool,
        message: str,
        transaction_ref: str,
    ) -> None:
        tx = PaymentTransaction(
            session_id=session_id,
            plate_number=plate,
            amount=Decimal(str(amount)),
            payment_method=payment_method,
            success=success,
            message=message,
            transaction_ref=transaction_ref,
            verified_at=utc_now(),
        )
        self.db.add(tx)

    def process_webhook(self, payload: PaymentWebhookIn) -> PaymentVerifyOut:
        """Called by ABA/KHQR payment gateway or exit payment terminal."""
        if not payload.success:
            return PaymentVerifyOut(success=False, message="Payment not successful.")

        invoice = self.invoice_service.get_by_id(payload.invoice_id)
        if not invoice:
            return PaymentVerifyOut(success=False, message="Invoice not found.")

        session = self.parking_service.get_by_id(invoice.session_id)
        if not session:
            return PaymentVerifyOut(success=False, message="Parking session not found.")

        expected = float(session.fee_amount or invoice.amount or 0)
        if expected and round(expected, 2) != round(payload.amount, 2):
            return PaymentVerifyOut(
                success=False,
                message=f"Amount mismatch. Expected ${expected:.2f}, received ${payload.amount:.2f}.",
            )

        tx_ref = payload.transaction_ref or next_transaction_ref(self.db)
        plate = session.license_plate
        if session.status != "Completed":
            self.parking_service.close_session(session)
        invoice.amount = Decimal(str(payload.amount))
        self.invoice_service.mark_paid(invoice, payload.payment_method, tx_ref)
        self._save_transaction(
            session.id,
            plate,
            payload.amount,
            payload.payment_method,
            True,
            "Payment confirmed via webhook.",
            tx_ref,
        )
        self.db.commit()
        return PaymentVerifyOut(
            success=True,
            message="Payment confirmed via webhook.",
            transaction_ref=tx_ref,
        )

    @staticmethod
    def _simulate_gateway_success(payment_method: str, amount: float) -> bool:
        # Placeholder until real ABA/KHQR webhooks are integrated.
        return amount > 0 and bool(payment_method)
