"""Shared fixtures for Mercado Pago plugin tests."""
import pytest

from vbwd.sdk.interface import SDKConfig


@pytest.fixture
def mp_config() -> dict:
    return {
        "sandbox": True,
        "countries": {
            "BR": {
                "enabled": True,
                "access_token": "TEST-BR-TOKEN",
                "public_key": "APP_USR-BR-PK",
                "webhook_secret": "whsec-br-abc",
            },
            "MX": {
                "enabled": True,
                "access_token": "TEST-MX-TOKEN",
                "public_key": "APP_USR-MX-PK",
                "webhook_secret": "whsec-mx-abc",
            },
        },
        "default_country": "BR",
        "max_installments": 12,
    }


@pytest.fixture
def sdk_config_br(mp_config) -> SDKConfig:
    return SDKConfig(
        api_key=mp_config["countries"]["BR"]["access_token"],
        sandbox=True,
    )


@pytest.fixture
def adapter_br(sdk_config_br, mp_config):
    from plugins.mercado_pago.mercado_pago.sdk_adapter import (
        MercadoPagoSDKAdapter,
    )

    return MercadoPagoSDKAdapter(
        config=sdk_config_br,
        country="BR",
        public_key=mp_config["countries"]["BR"]["public_key"],
        webhook_secret=mp_config["countries"]["BR"]["webhook_secret"],
    )
