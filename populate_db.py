"""Idempotent demo data for Mercado Pago."""
from decimal import Decimal

from vbwd.extensions import db

from plugins.mercado_pago.mercado_pago.models import MercadoPagoPayment


def populate_db() -> None:
    existing = (
        db.session.query(MercadoPagoPayment)
        .filter_by(invoice_no="DEMO-MP-0001")
        .one_or_none()
    )
    if existing is not None:
        return

    db.session.add(
        MercadoPagoPayment(
            invoice_no="DEMO-MP-0001",
            country="BR",
            preference_id="PREF-DEMO-BR-1",
            mp_payment_id="987654321",
            method="pix",
            amount=Decimal("99.00"),
            currency="BRL",
            installments=1,
            status="completed",
            last_provider_status="approved",
            extra_data={"demo": True},
        )
    )
    db.session.commit()


if __name__ == "__main__":
    populate_db()
