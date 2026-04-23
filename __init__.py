"""Mercado Pago plugin — LATAM regional aggregator (Pix, Boleto, OXXO, SPEI, PSE, Webpay, cards + installments)."""
from typing import Optional, Dict, Any, TYPE_CHECKING
from decimal import Decimal
from uuid import UUID

from vbwd.plugins.base import PluginMetadata
from vbwd.plugins.payment_provider import (
    PaymentProviderPlugin,
    PaymentResult,
    PaymentStatus,
)

if TYPE_CHECKING:
    from flask import Blueprint


SUPPORTED_COUNTRIES = ("BR", "MX", "AR", "CO", "CL", "UY", "PE")

COUNTRY_CURRENCY = {
    "BR": "BRL",
    "MX": "MXN",
    "AR": "ARS",
    "CO": "COP",
    "CL": "CLP",
    "UY": "UYU",
    "PE": "PEN",
}


DEFAULT_CONFIG = {
    "sandbox": True,
    "countries": {
        country: {
            "enabled": False,
            "access_token": "",
            "public_key": "",
            "webhook_secret": "",
        }
        for country in SUPPORTED_COUNTRIES
    },
    "default_country": "BR",
    "max_installments": 12,
    "min_installments": 1,
    "pass_interest_to_buyer": False,
    "boleto_expiry_days": 3,
    "oxxo_expiry_days": 3,
    "spei_expiry_days": 1,
}


class MercadoPagoPlugin(PaymentProviderPlugin):
    """Mercado Pago — one plugin, 7 LATAM countries.

    Class MUST live in __init__.py per plugin-discovery rule.
    """

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="mercado_pago",
            version="1.0.0",
            author="VBWD Team",
            description=(
                "Mercado Pago — regional LATAM PSP covering Pix, Boleto, "
                "OXXO, SPEI, PSE, Webpay, PagoEfectivo, RapiPago, and "
                "cards with parcelamento/MSI installments across BR, MX, "
                "AR, CO, CL, UY, PE."
            ),
            dependencies=[],
        )

    def initialize(self, config: Optional[Dict[str, Any]] = None) -> None:
        merged = _deep_merge(DEFAULT_CONFIG, config or {})
        super().initialize(merged)

    def get_blueprint(self) -> Optional["Blueprint"]:
        from plugins.mercado_pago.mercado_pago.routes import mp_plugin_bp

        return mp_plugin_bp

    def get_url_prefix(self) -> Optional[str]:
        return "/api/v1/plugins/mercado-pago"

    @property
    def admin_permissions(self):
        return [
            {
                "key": "payments.configure",
                "label": "Payment provider settings",
                "group": "Payments",
            },
        ]

    def on_enable(self) -> None:
        pass

    def on_disable(self) -> None:
        pass

    def _get_adapter_for_country(self, country: str):
        from flask import current_app
        from plugins.mercado_pago.mercado_pago.sdk_adapter import (
            MercadoPagoSDKAdapter,
        )
        from vbwd.sdk.interface import SDKConfig

        if country not in SUPPORTED_COUNTRIES:
            raise ValueError(
                f"Unsupported Mercado Pago country: {country}. "
                f"Supported: {SUPPORTED_COUNTRIES}"
            )

        config_store = current_app.config_store
        config = config_store.get_config("mercado_pago")
        country_cfg = config.get("countries", {}).get(country, {})
        if not country_cfg.get("enabled"):
            raise ValueError(f"Mercado Pago {country} not enabled")

        return MercadoPagoSDKAdapter(
            SDKConfig(
                api_key=country_cfg.get("access_token", ""),
                sandbox=config.get("sandbox", True),
            ),
            country=country,
            public_key=country_cfg.get("public_key", ""),
            webhook_secret=country_cfg.get("webhook_secret", ""),
        )

    def create_payment_intent(
        self,
        amount: Decimal,
        currency: str,
        subscription_id: UUID,
        user_id: UUID,
        metadata: Optional[Dict[str, Any]] = None,
        capture: bool = True,
    ) -> PaymentResult:
        metadata = metadata or {}
        country = (metadata.get("country") or "").upper()
        if country not in SUPPORTED_COUNTRIES:
            return PaymentResult(
                success=False,
                status=PaymentStatus.FAILED,
                error_message=(
                    f"country must be one of {SUPPORTED_COUNTRIES}; "
                    f"got {country!r}"
                ),
            )
        expected_currency = COUNTRY_CURRENCY[country]
        if currency.upper() != expected_currency:
            return PaymentResult(
                success=False,
                status=PaymentStatus.FAILED,
                error_message=(
                    f"Mercado Pago {country} requires currency "
                    f"{expected_currency}, got {currency}"
                ),
            )

        adapter = self._get_adapter_for_country(country)
        response = adapter.create_preference(
            amount=amount,
            currency=currency,
            invoice_no=str(subscription_id),
            user_id=str(user_id),
            method=metadata.get("method"),
            installments=metadata.get("installments"),
            metadata=metadata,
        )
        if not response.success:
            return PaymentResult(
                success=False,
                error_message=response.error,
                status=PaymentStatus.FAILED,
            )
        return PaymentResult(
            success=True,
            transaction_id=response.data.get("id"),
            status=PaymentStatus.PENDING,
            metadata={
                "preference_id": response.data.get("id"),
                "init_point": response.data.get("init_point"),
                "qr_payload": response.data.get("qr_payload"),
                "voucher_url": response.data.get("voucher_url"),
                "country": country,
            },
        )

    def capture_payment(
        self, payment_id: str, amount: Optional[Decimal] = None
    ) -> PaymentResult:
        return PaymentResult(
            success=False,
            status=PaymentStatus.FAILED,
            error_message=(
                "Mercado Pago captures via preference flow; use "
                "get_payment_status to poll."
            ),
        )

    def release_authorization(self, payment_id: str) -> PaymentResult:
        return PaymentResult(
            success=False,
            status=PaymentStatus.FAILED,
            error_message=(
                "Mercado Pago does not support generic authorization hold "
                "via preference flow."
            ),
        )

    def process_payment(
        self, payment_intent_id: str, payment_method: str
    ) -> PaymentResult:
        return PaymentResult(
            success=False,
            status=PaymentStatus.FAILED,
            error_message=(
                "Mercado Pago finalises payment via user redirect — use "
                "status polling + webhooks."
            ),
        )

    def refund_payment(
        self, transaction_id: str, amount: Optional[Decimal] = None
    ) -> PaymentResult:
        return PaymentResult(
            success=False,
            status=PaymentStatus.FAILED,
            error_message=(
                "Refund requires country context — call the admin refund "
                "route which looks up the stored country."
            ),
        )

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        # Webhook verification is per-country; actual check happens in
        # the route after it resolves the country from the payload.
        return False

    def handle_webhook(self, payload: Dict[str, Any]) -> None:
        from plugins.mercado_pago.mercado_pago.services import (
            MercadoPagoWebhookHandler,
        )

        handler = MercadoPagoWebhookHandler()
        handler.handle(payload)


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Merge override into a shallow copy of base, recursing into dicts."""
    result = {**base}
    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
