"""Unit tests for MercadoPagoService + MercadoPagoWebhookHandler."""
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from plugins.mercado_pago.mercado_pago.services import (
    MercadoPagoService,
    MercadoPagoWebhookHandler,
    compute_installment_plans,
    map_mp_status,
)


class TestMpStatus:
    @pytest.mark.parametrize(
        "provider,expected",
        [
            ("approved", "completed"),
            ("authorized", "authorized"),
            ("in_process", "processing"),
            ("in_mediation", "processing"),
            ("pending", "pending"),
            ("rejected", "failed"),
            ("cancelled", "cancelled"),
            ("refunded", "refunded"),
            ("charged_back", "refunded"),
            ("unknown", "failed"),
            ("", "failed"),
        ],
    )
    def test_maps(self, provider, expected):
        assert map_mp_status(provider) == expected


class TestInstallmentPlans:
    def test_br_allows_up_to_12(self):
        plans = compute_installment_plans(Decimal("1200"), "BR", max_installments=12)
        assert plans == list(range(1, 13))

    def test_mx_msi_brands(self):
        plans = compute_installment_plans(Decimal("1200"), "MX", card_brand="visa")
        assert plans == [1, 3, 6, 9, 12]

    def test_mx_non_msi_brand_single_payment(self):
        plans = compute_installment_plans(Decimal("1200"), "MX", card_brand="carnet")
        assert plans == [1]

    def test_andean_capped_at_6(self):
        for country in ("CO", "CL", "PE"):
            plans = compute_installment_plans(Decimal("1000"), country)
            assert plans == [1, 2, 3, 4, 5, 6]

    def test_unknown_country_single_payment(self):
        plans = compute_installment_plans(Decimal("1"), "ZZ")
        assert plans == [1]


class TestService:
    def test_record_preference_created(self):
        session = MagicMock()
        session.query.return_value.filter_by.return_value.one_or_none.return_value = (
            None
        )
        service = MercadoPagoService(session=session)

        payment = service.record_preference_created(
            invoice_no="INV-1",
            country="BR",
            preference_id="PREF-1",
            amount=Decimal("100"),
            currency="BRL",
            method="pix",
            installments=None,
        )

        assert payment.invoice_no == "INV-1"
        assert payment.country == "BR"
        assert payment.preference_id == "PREF-1"
        assert payment.status == "pending"
        session.add.assert_called_once()
        session.commit.assert_called_once()

    def test_apply_provider_update(self):
        existing = MagicMock()
        existing.status = "pending"
        existing.last_provider_status = None
        existing.mp_payment_id = None
        session = MagicMock()
        session.query.return_value.filter_by.return_value.one_or_none.return_value = (
            existing
        )

        service = MercadoPagoService(session=session)
        service.apply_provider_update("INV-1", {"status": "approved", "id": 987654})

        assert existing.status == "completed"
        assert existing.last_provider_status == "approved"
        assert existing.mp_payment_id == "987654"
        session.commit.assert_called()

    def test_apply_provider_update_idempotent(self):
        existing = MagicMock()
        existing.status = "completed"
        existing.last_provider_status = "approved"
        existing.mp_payment_id = "987654"
        session = MagicMock()
        session.query.return_value.filter_by.return_value.one_or_none.return_value = (
            existing
        )

        service = MercadoPagoService(session=session)
        service.apply_provider_update("INV-1", {"status": "approved", "id": 987654})
        session.commit.assert_not_called()


class TestWebhookHandler:
    def test_rejects_missing_external_ref(self):
        handler = MercadoPagoWebhookHandler(service=MagicMock())
        with pytest.raises(ValueError, match="external_reference"):
            handler.handle({"status": "approved", "id": 1})

    def test_accepts_external_reference(self):
        svc = MagicMock()
        handler = MercadoPagoWebhookHandler(service=svc)
        handler.handle({"external_reference": "INV-1", "status": "approved", "id": 1})
        svc.apply_provider_update.assert_called_once()

    def test_fallback_to_invoice_no_alias(self):
        svc = MagicMock()
        handler = MercadoPagoWebhookHandler(service=svc)
        handler.handle({"invoice_no": "INV-1", "status": "approved"})
        svc.apply_provider_update.assert_called_once()
