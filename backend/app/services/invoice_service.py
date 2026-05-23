from datetime import date
from decimal import Decimal

from sqlalchemy import String, asc, cast, desc, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.invoice import Invoice
from app.schemas.invoice import InvoiceOut
from app.utils.datetime_utils import format_display_datetime, utc_now
from app.utils.exit_verify_utils import generate_exit_verify_hash
from app.utils.id_generator import next_invoice_id


class InvoiceService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_pending(
        self,
        session_id: str,
        license_plate: str,
        amount: Decimal | None = None,
    ) -> Invoice:
        now = utc_now()
        invoice_id = next_invoice_id(self.db)
        settings = get_settings()
        verify_hash = generate_exit_verify_hash(
            invoice_id=invoice_id,
            session_id=session_id,
            license_plate=license_plate,
            secret=settings.exit_verify_secret,
        )
        invoice = Invoice(
            id=invoice_id,
            session_id=session_id,
            invoice_date=date.today(),
            license_plate=license_plate,
            amount=amount or Decimal("0.00"),
            method="KHQR",
            status="Pending",
            exit_verify_hash=verify_hash,
            created_at=now,
        )
        self.db.add(invoice)
        self.db.flush()
        return invoice

    def get_by_id(self, invoice_id: str) -> Invoice | None:
        return self.db.get(Invoice, invoice_id)

    def get_by_verify_hash(self, verify_hash: str) -> Invoice | None:
        normalized = verify_hash.strip().upper()
        return (
            self.db.query(Invoice)
            .filter(Invoice.exit_verify_hash == normalized)
            .first()
        )

    def list_invoices(
        self,
        *,
        page: int,
        limit: int,
        sort_by: str | None,
        sort_order: str | None,
        search: str | None,
        status: list[str] | None,
        method: list[str] | None,
        start_date: date | None,
        end_date: date | None,
    ) -> tuple[list[InvoiceOut], int, dict[str, float]]:
        query = select(Invoice)
        filters = []

        if search:
            term = f"%{search.lower()}%"
            filters.append(
                or_(
                    func.lower(Invoice.id).like(term),
                    func.lower(Invoice.license_plate).like(term),
                    cast(Invoice.amount, String).like(term),
                )
            )
        if status:
            filters.append(Invoice.status.in_(status))
        if method:
            filters.append(Invoice.method.in_(method))
        if start_date:
            filters.append(Invoice.invoice_date >= start_date)
        if end_date:
            filters.append(Invoice.invoice_date <= end_date)

        count_stmt = select(func.count()).select_from(Invoice)
        if filters:
            count_stmt = count_stmt.where(*filters)
            query = query.where(*filters)

        sort_map = {
            "id": Invoice.id,
            "date": Invoice.invoice_date,
            "plate": Invoice.license_plate,
            "amount": Invoice.amount,
            "method": Invoice.method,
            "status": Invoice.status,
        }
        sort_col = sort_map.get(sort_by or "date", Invoice.invoice_date)
        order_fn = desc if sort_order == "desc" else asc
        query = query.order_by(order_fn(sort_col))

        total = self.db.scalar(count_stmt) or 0
        rows = self.db.scalars(query.offset((page - 1) * limit).limit(limit)).all()

        paid_sum = sum(float(r.amount) for r in rows if r.status == "Paid")
        aggregates = {"paidAmount": paid_sum}

        return [self._to_out(row) for row in rows], int(total), aggregates

    def _to_out(self, invoice: Invoice) -> InvoiceOut:
        session = invoice.session
        entry_time = (
            format_display_datetime(session.entry_time, with_am_pm=True)
            if session and session.entry_time
            else invoice.invoice_date.isoformat()
        )
        exit_time = (
            format_display_datetime(session.exit_time, with_am_pm=True)
            if session and session.exit_time
            else None
        )
        return InvoiceOut(
            id=invoice.id,
            date=invoice.invoice_date.isoformat(),
            plate=invoice.license_plate,
            amount=f"${float(invoice.amount):.2f}",
            method=invoice.method,  # type: ignore[arg-type]
            status=invoice.status,  # type: ignore[arg-type]
            entry_time=entry_time,
            exit_time=exit_time,
        )

    def mark_paid(self, invoice: Invoice, method: str, transaction_ref: str) -> Invoice:
        invoice.status = "Paid"
        invoice.method = self._normalize_method(method)
        invoice.transaction_ref = transaction_ref
        self.db.add(invoice)
        return invoice

    @staticmethod
    def _normalize_method(payment_method: str) -> str:
        upper = payment_method.upper()
        if "ABA" in upper:
            return "ABA"
        if "KHQR" in upper or "QR" in upper:
            return "KHQR"
        return "Cash"
