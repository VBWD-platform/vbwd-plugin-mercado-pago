"""Mercado Pago payment record — one per invoice with country context."""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, Numeric, String

from vbwd.extensions import db


class MercadoPagoPayment(db.Model):
    __tablename__ = "mercado_pago_payments"

    id = Column(
        db.UUID,
        primary_key=True,
        server_default=db.text("gen_random_uuid()"),
    )
    invoice_no = Column(String(64), nullable=False, unique=True, index=True)
    country = Column(String(2), nullable=False, index=True)
    preference_id = Column(String(128), nullable=True)
    mp_payment_id = Column(String(128), nullable=True, index=True)
    method = Column(String(32), nullable=True)
    amount = Column(Numeric(14, 2), nullable=False)
    currency = Column(String(3), nullable=False)
    installments = Column(Integer, nullable=True)
    status = Column(String(24), nullable=False, default="pending")
    last_provider_status = Column(String(32), nullable=True)
    extra_data = Column(db.JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "invoice_no": self.invoice_no,
            "country": self.country,
            "preference_id": self.preference_id,
            "mp_payment_id": self.mp_payment_id,
            "method": self.method,
            "amount": str(self.amount),
            "currency": self.currency,
            "installments": self.installments,
            "status": self.status,
            "last_provider_status": self.last_provider_status,
            "extra_data": self.extra_data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
