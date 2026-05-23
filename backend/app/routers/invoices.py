from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.invoice import InvoiceExitBarcodeOut, InvoiceListResult
from app.services.invoice_service import InvoiceService
from app.utils.exit_verify_utils import barcode_data_url

router = APIRouter(prefix="/api/invoices", tags=["invoices"])


@router.get("", response_model=InvoiceListResult)
def list_invoices(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    sort_by: str | None = Query(None, alias="sortBy"),
    sort_order: str | None = Query(None, alias="sortOrder"),
    search: str | None = None,
    status: list[str] | None = Query(None),
    method: list[str] | None = Query(None),
    start_date: date | None = Query(None, alias="startDate"),
    end_date: date | None = Query(None, alias="endDate"),
    db: Session = Depends(get_db),
) -> InvoiceListResult:
    data, total, aggregates = InvoiceService(db).list_invoices(
        page=page,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        search=search,
        status=status,
        method=method,
        start_date=start_date,
        end_date=end_date,
    )
    return InvoiceListResult(data=data, total=total, aggregates=aggregates)


@router.get("/{invoice_id}/exit-barcode", response_model=InvoiceExitBarcodeOut)
def invoice_exit_barcode(invoice_id: str, db: Session = Depends(get_db)) -> InvoiceExitBarcodeOut:
    """Code128 barcode for exit gate — scan hash + plate at POST /api/iot/exit-verify."""
    invoice = InvoiceService(db).get_by_id(invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")
    if not invoice.exit_verify_hash:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exit verification code not generated for this invoice.",
        )
    code = invoice.exit_verify_hash
    return InvoiceExitBarcodeOut(
        invoice_id=invoice.id,
        verify_hash=code,
        barcode_image=barcode_data_url(code),
        plate=invoice.license_plate,
    )
