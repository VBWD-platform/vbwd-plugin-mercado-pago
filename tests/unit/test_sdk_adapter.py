"""Unit tests for MercadoPagoSDKAdapter (TDD-first per sprint checkpoints)."""
from decimal import Decimal
from unittest.mock import MagicMock


class TestCreatePreference:
    def test_success(self, adapter_br, mocker):
        fake = MagicMock()
        fake.status_code = 201
        fake.json.return_value = {
            "id": "PREF-1",
            "init_point": "https://mp.test/pref/PREF-1",
            "sandbox_init_point": "https://sandbox.mp.test/pref/PREF-1",
        }
        mocker.patch(
            "plugins.mercado_pago.mercado_pago.sdk_adapter.requests.post",
            return_value=fake,
        )

        resp = adapter_br.create_preference(
            amount=Decimal("100.00"),
            currency="BRL",
            invoice_no="INV-1",
            user_id="user-1",
            metadata={"return_url": "https://shop.test/ok"},
        )
        assert resp.success is True
        assert resp.data["id"] == "PREF-1"

    def test_4xx_returns_provider_message(self, adapter_br, mocker):
        fake = MagicMock()
        fake.status_code = 400
        fake.json.return_value = {"message": "invalid_token"}
        mocker.patch(
            "plugins.mercado_pago.mercado_pago.sdk_adapter.requests.post",
            return_value=fake,
        )
        resp = adapter_br.create_preference(
            amount=Decimal("1"),
            currency="BRL",
            invoice_no="INV-1",
            user_id="user-1",
        )
        assert resp.success is False
        assert "invalid_token" in (resp.error or "")

    def test_network_error(self, adapter_br, mocker):
        import requests

        mocker.patch(
            "plugins.mercado_pago.mercado_pago.sdk_adapter.requests.post",
            side_effect=requests.ConnectionError("down"),
        )
        resp = adapter_br.create_preference(
            amount=Decimal("1"),
            currency="BRL",
            invoice_no="INV-1",
            user_id="user-1",
        )
        assert resp.success is False
        assert "network" in (resp.error or "")

    def test_5xx_failure(self, adapter_br, mocker):
        fake = MagicMock()
        fake.status_code = 503
        fake.text = "upstream down"
        mocker.patch(
            "plugins.mercado_pago.mercado_pago.sdk_adapter.requests.post",
            return_value=fake,
        )
        resp = adapter_br.create_preference(
            amount=Decimal("1"),
            currency="BRL",
            invoice_no="INV-1",
            user_id="user-1",
        )
        assert resp.success is False
        assert "503" in (resp.error or "")

    def test_installments_propagate(self, adapter_br, mocker):
        captured = {}

        def _fake_post(url, json, headers, timeout):
            captured["json"] = json
            fake = MagicMock()
            fake.status_code = 201
            fake.json.return_value = {"id": "PREF-x"}
            return fake

        mocker.patch(
            "plugins.mercado_pago.mercado_pago.sdk_adapter.requests.post",
            side_effect=_fake_post,
        )
        adapter_br.create_preference(
            amount=Decimal("1200"),
            currency="BRL",
            invoice_no="INV-1",
            user_id="user-1",
            installments=6,
        )
        assert captured["json"]["payment_methods"]["installments"] == 6


class TestVerifyWebhook:
    def test_accepts_valid_signature(self, adapter_br):
        import hashlib
        import hmac

        body = b'{"type":"payment"}'
        signature = hmac.new(
            b"whsec-br-abc", body, hashlib.sha256
        ).hexdigest()
        assert adapter_br.verify_webhook(body, signature) is True

    def test_rejects_wrong_signature(self, adapter_br):
        assert adapter_br.verify_webhook(b"body", "dead") is False

    def test_rejects_empty_signature(self, adapter_br):
        assert adapter_br.verify_webhook(b"body", "") is False


class TestLiskov:
    def test_capture_returns_unsupported(self, adapter_br):
        resp = adapter_br.capture_payment("PAY-1")
        assert resp.success is False

    def test_release_returns_unsupported(self, adapter_br):
        resp = adapter_br.release_authorization("PAY-1")
        assert resp.success is False
