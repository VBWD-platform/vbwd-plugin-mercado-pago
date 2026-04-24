"""Mercado Pago services — domain mapping + webhook handling."""
from decimal import Decimal
from typing import Any, Dict, Optional

from vbwd.extensions import db

from plugins.mercado_pago.mercado_pago.models import MercadoPagoPayment


STATUS_MAP = {
    "approved": "completed",
    "authorized": "authorized",
    "in_process": "processing",
    "in_mediation": "processing",
    "pending": "pending",
    "rejected": "failed",
    "cancelled": "cancelled",
    "refunded": "refunded",
    "charged_back": "refunded",
}


def map_mp_status(provider_status: str) -> str:
    if not provider_status:
        return "failed"
    return STATUS_MAP.get(provider_status.lower(), "failed")


def compute_installment_plans(
    amount: Decimal,
    country: str,
    card_brand: Optional[str] = None,
    max_installments: int = 12,
) -> list[int]:
    """Return valid installment counts per country + brand.

    Simplified rules — real MSI tables are bin-dependent; this is the
    baseline. Refined per-merchant via config.
    """
    if country == "BR":
        return list(range(1, max_installments + 1))
    if country == "MX":
        if card_brand in ("visa", "mastercard", "amex"):
            return [1, 3, 6, 9, 12]
        return [1]
    if country in ("AR", "CO", "CL", "UY", "PE"):
        return list(range(1, min(max_installments, 6) + 1))
    return [1]


class MercadoPagoService:
    """Ingest MP responses into the MercadoPagoPayment domain."""

    def __init__(self, session=None):
        self._session = session or db.session

    def record_preference_created(
        self,
        invoice_no: str,
        country: str,
        preference_id: str,
        amount: Decimal,
        currency: str,
        method: Optional[str] = None,
        installments: Optional[int] = None,
        extra_data: Optional[Dict[str, Any]] = None,
    ) -> MercadoPagoPayment:
        payment = self._get_or_create(invoice_no)
        payment.country = country
        payment.preference_id = preference_id
        payment.amount = amount
        payment.currency = currency
        payment.method = method
        payment.installments = installments
        payment.status = "pending"
        payment.extra_data = extra_data
        self._session.add(payment)
        self._session.commit()
        return payment

    def apply_provider_update(
        self, invoice_no: str, provider_payload: Dict[str, Any]
    ) -> MercadoPagoPayment:
        payment = self._get_or_create(invoice_no)
        provider_status = provider_payload.get("status", "")
        new_status = map_mp_status(provider_status)
        incoming_id = provider_payload.get("id")
        incoming_id_str = str(incoming_id) if incoming_id is not None else None
        effective_id = incoming_id_str or payment.mp_payment_id

        if (
            payment.status == new_status
            and payment.last_provider_status == provider_status
            and payment.mp_payment_id == effective_id
        ):
            return payment

        payment.status = new_status
        payment.last_provider_status = provider_status
        if incoming_id_str is not None:
            payment.mp_payment_id = incoming_id_str
        self._session.commit()
        return payment

    def _get_or_create(self, invoice_no: str) -> MercadoPagoPayment:
        payment = (
            self._session.query(MercadoPagoPayment)
            .filter_by(invoice_no=invoice_no)
            .one_or_none()
        )
        if payment is None:
            payment = MercadoPagoPayment(
                invoice_no=invoice_no,
                country="",
                amount=Decimal("0"),
                currency="",
            )
        return payment


class MercadoPagoWebhookHandler:
    """Webhook handler — idempotent by (invoice_no, provider_status, id)."""

    def __init__(self, service: Optional[MercadoPagoService] = None):
        self._service = service or MercadoPagoService()

    def handle(self, payload: Dict[str, Any]) -> MercadoPagoPayment:
        invoice_no = payload.get("external_reference") or payload.get("invoice_no")
        if not invoice_no:
            raise ValueError("missing external_reference in Mercado Pago webhook")
        return self._service.apply_provider_update(invoice_no, payload)
