"""Mercado Pago SDK adapter — per-country access token + preference API."""
import hashlib
import hmac
from decimal import Decimal
from typing import Any, Dict, Optional

import requests

from vbwd.sdk.base import BaseSDKAdapter
from vbwd.sdk.interface import SDKConfig, SDKResponse


MP_API_HOST = "https://api.mercadopago.com"


class MercadoPagoSDKAdapter(BaseSDKAdapter):
    """Mercado Pago adapter.

    One instance = one country. The plugin picks the right adapter per
    request based on merchant configuration. Liskov-compliant:
    SDKResponse.success reflects HTTP success + response parse.
    """

    def __init__(
        self,
        config: SDKConfig,
        country: str,
        public_key: str = "",
        webhook_secret: str = "",
        idempotency_service=None,
    ):
        super().__init__(config, idempotency_service)
        self._country = country
        self._access_token = config.api_key
        self._public_key = public_key
        self._webhook_secret = webhook_secret

    @property
    def provider_name(self) -> str:
        return "mercado_pago"

    @property
    def country(self) -> str:
        return self._country

    def create_payment_intent(
        self,
        amount: Decimal,
        currency: str,
        metadata: Dict[str, Any],
        idempotency_key: Optional[str] = None,
    ) -> SDKResponse:
        return self.create_preference(
            amount=amount,
            currency=currency,
            invoice_no=metadata.get("invoice_no", ""),
            user_id=metadata.get("user_id", ""),
            method=metadata.get("method"),
            installments=metadata.get("installments"),
            metadata=metadata,
        )

    def capture_payment(
        self,
        payment_intent_id: str,
        idempotency_key: Optional[str] = None,
    ) -> SDKResponse:
        return SDKResponse(
            success=False,
            error=(
                "Mercado Pago captures on user redirect; use get_payment_status"
            ),
        )

    def release_authorization(self, payment_intent_id: str) -> SDKResponse:
        return SDKResponse(
            success=False,
            error="Mercado Pago preferences do not support release",
        )

    def get_payment_status(self, payment_intent_id: str) -> SDKResponse:
        return self._get(f"/v1/payments/{payment_intent_id}")

    def create_preference(
        self,
        amount: Decimal,
        currency: str,
        invoice_no: str,
        user_id: str,
        method: Optional[str] = None,
        installments: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SDKResponse:
        """Create a Mercado Pago preference.

        Returns `{ id, init_point, sandbox_init_point, qr_payload?,
        voucher_url? }`.
        """
        metadata = metadata or {}
        payload: Dict[str, Any] = {
            "external_reference": invoice_no,
            "items": [
                {
                    "title": metadata.get("description", "Payment"),
                    "quantity": 1,
                    "currency_id": currency,
                    "unit_price": float(amount),
                }
            ],
            "back_urls": {
                "success": metadata.get("return_url", ""),
                "pending": metadata.get("return_url", ""),
                "failure": metadata.get("cancel_url", ""),
            },
            "auto_return": "approved",
            "payer": {"id": user_id},
            "notification_url": metadata.get("webhook_url", ""),
        }
        if installments:
            payload["payment_methods"] = {
                "installments": installments,
                "default_installments": installments,
            }
        if method:
            payload["payment_methods"] = payload.get("payment_methods", {})
            payload["payment_methods"]["excluded_payment_types"] = [
                {"id": t}
                for t in ("credit_card", "debit_card", "ticket", "atm")
                if t != method
            ]

        return self._post("/checkout/preferences", payload)

    def refund_payment(
        self,
        payment_intent_id: str,
        amount: Optional[Decimal] = None,
        idempotency_key: Optional[str] = None,
    ) -> SDKResponse:
        payload: Dict[str, Any] = {}
        if amount is not None:
            payload["amount"] = float(amount)
        return self._post(
            f"/v1/payments/{payment_intent_id}/refunds", payload
        )

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """Verify Mercado Pago webhook signature header.

        MP sends an HMAC-SHA256 signature in `x-signature` header, keyed
        by the merchant's webhook secret.
        """
        if not self._webhook_secret or not signature:
            return False
        expected = hmac.new(
            self._webhook_secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    # ── internal helpers ────────────────────────────────────────────────

    def _post(self, path: str, body: Dict[str, Any]) -> SDKResponse:
        try:
            resp = requests.post(
                f"{MP_API_HOST}{path}",
                json=body,
                headers=self._auth_headers(),
                timeout=30,
            )
        except requests.RequestException as exc:
            return SDKResponse(success=False, error=f"network: {exc}")
        return self._parse(resp)

    def _get(self, path: str) -> SDKResponse:
        try:
            resp = requests.get(
                f"{MP_API_HOST}{path}",
                headers=self._auth_headers(),
                timeout=30,
            )
        except requests.RequestException as exc:
            return SDKResponse(success=False, error=f"network: {exc}")
        return self._parse(resp)

    def _parse(self, resp: requests.Response) -> SDKResponse:
        if resp.status_code >= 500:
            return SDKResponse(
                success=False,
                error=f"Mercado Pago {resp.status_code}: {resp.text[:200]}",
            )
        try:
            body = resp.json()
        except ValueError:
            return SDKResponse(
                success=False, error="invalid JSON from Mercado Pago"
            )
        if resp.status_code >= 400:
            return SDKResponse(
                success=False,
                data=body,
                error=body.get("message", f"HTTP {resp.status_code}"),
            )
        return SDKResponse(success=True, data=body)

    def _auth_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
