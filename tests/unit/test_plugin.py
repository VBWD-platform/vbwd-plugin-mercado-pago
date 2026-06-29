"""Plugin tests — country/currency guard + Liskov initialize merge."""
from decimal import Decimal
from uuid import uuid4

from vbwd.plugins.base import PluginStatus

from plugins.mercado_pago import (
    MercadoPagoPlugin,
    DEFAULT_CONFIG,
    COUNTRY_CURRENCY,
)


class TestMercadoPagoPlugin:
    def test_metadata(self):
        plugin = MercadoPagoPlugin()
        assert plugin.metadata.name == "mercado_pago"
        assert plugin.metadata.version == "26.6.1"

    def test_initialize_deep_merges_country_config(self):
        plugin = MercadoPagoPlugin()
        plugin.initialize(
            {
                "countries": {
                    "BR": {"enabled": True, "access_token": "BR-T"},
                }
            }
        )
        assert plugin.status == PluginStatus.INITIALIZED
        assert plugin._config["countries"]["BR"]["enabled"] is True
        assert plugin._config["countries"]["BR"]["access_token"] == "BR-T"
        assert plugin._config["countries"]["MX"]["enabled"] is False
        assert plugin._config["default_country"] == DEFAULT_CONFIG["default_country"]

    def test_rejects_unsupported_country(self):
        plugin = MercadoPagoPlugin()
        plugin.initialize({})
        result = plugin.create_payment_intent(
            amount=Decimal("10"),
            currency="USD",
            subscription_id=uuid4(),
            user_id=uuid4(),
            metadata={"country": "ZZ"},
        )
        assert result.success is False
        assert "country must be one of" in (result.error_message or "")

    def test_rejects_mismatched_currency(self):
        plugin = MercadoPagoPlugin()
        plugin.initialize({})
        result = plugin.create_payment_intent(
            amount=Decimal("10"),
            currency="USD",
            subscription_id=uuid4(),
            user_id=uuid4(),
            metadata={"country": "BR"},
        )
        assert result.success is False
        assert "BRL" in (result.error_message or "")

    def test_country_currency_map_complete(self):
        from plugins.mercado_pago import SUPPORTED_COUNTRIES

        for country in SUPPORTED_COUNTRIES:
            assert country in COUNTRY_CURRENCY
