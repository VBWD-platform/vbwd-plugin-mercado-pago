"""Mercado Pago plugin API routes."""
import logging
from decimal import Decimal

from flask import Blueprint, current_app, jsonify, request

from vbwd.middleware.auth import require_auth

from plugins.mercado_pago.mercado_pago.services import (
    MercadoPagoService,
    MercadoPagoWebhookHandler,
)

logger = logging.getLogger(__name__)

mp_plugin_bp = Blueprint("mp_plugin", __name__)


def _get_plugin():
    manager = current_app.plugin_manager
    plugin = manager.get_plugin("mercado_pago")
    if plugin is None:
        raise RuntimeError("mercado_pago plugin not enabled")
    return plugin


@mp_plugin_bp.route("/preferences", methods=["POST"])
@require_auth
def create_preference():
    body = request.get_json(silent=True) or {}
    required = ("invoice_no", "amount", "currency", "country")
    missing = [f for f in required if not body.get(f)]
    if missing:
        return jsonify({"error": "missing fields", "fields": missing}), 400

    try:
        amount = Decimal(str(body["amount"]))
    except (ValueError, ArithmeticError):
        return jsonify({"error": "invalid amount"}), 400

    country = body["country"].upper()
    plugin = _get_plugin()
    try:
        adapter = plugin._get_adapter_for_country(country)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    response = adapter.create_preference(
        amount=amount,
        currency=body["currency"],
        invoice_no=body["invoice_no"],
        user_id=str(getattr(request, "user_id", "")),
        method=body.get("method"),
        installments=body.get("installments"),
        metadata={
            "description": body.get("description", "Payment"),
            "return_url": body.get("return_url"),
            "cancel_url": body.get("cancel_url"),
            "webhook_url": body.get("webhook_url"),
        },
    )
    if not response.success:
        return jsonify({"error": response.error or "MP error"}), 502

    service = MercadoPagoService()
    service.record_preference_created(
        invoice_no=body["invoice_no"],
        country=country,
        preference_id=response.data.get("id", ""),
        amount=amount,
        currency=body["currency"],
        method=body.get("method"),
        installments=body.get("installments"),
        extra_data=response.data,
    )

    return (
        jsonify(
            {
                "preference_id": response.data.get("id"),
                "init_point": response.data.get("init_point"),
                "sandbox_init_point": response.data.get("sandbox_init_point"),
            }
        ),
        201,
    )


@mp_plugin_bp.route("/payments/<invoice_no>/status", methods=["GET"])
@require_auth
def get_payment_status(invoice_no: str):
    from plugins.mercado_pago.mercado_pago.models import MercadoPagoPayment
    from vbwd.extensions import db

    payment = (
        db.session.query(MercadoPagoPayment)
        .filter_by(invoice_no=invoice_no)
        .one_or_none()
    )
    if payment is None:
        return jsonify({"error": "not found"}), 404

    if not payment.mp_payment_id:
        return jsonify(payment.to_dict()), 200

    plugin = _get_plugin()
    try:
        adapter = plugin._get_adapter_for_country(payment.country)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    response = adapter.get_payment_status(payment.mp_payment_id)
    if response.success:
        MercadoPagoService().apply_provider_update(invoice_no, response.data)

    return jsonify(payment.to_dict()), 200


@mp_plugin_bp.route("/webhooks/<country>", methods=["POST"])
def webhook(country: str):
    country = country.upper()
    plugin = _get_plugin()
    try:
        adapter = plugin._get_adapter_for_country(country)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    signature = request.headers.get("x-signature", "")
    if not adapter.verify_webhook(request.get_data(), signature):
        return jsonify({"error": "invalid signature"}), 401

    payload = request.get_json(silent=True) or {}

    if "data" in payload and payload.get("type") == "payment":
        payment_id = payload["data"].get("id")
        if payment_id:
            detail = adapter.get_payment_status(str(payment_id))
            if detail.success:
                handler = MercadoPagoWebhookHandler()
                handler.handle(detail.data)
    else:
        MercadoPagoWebhookHandler().handle(payload)

    return "", 204


@mp_plugin_bp.route("/payments/<invoice_no>/refund", methods=["POST"])
@require_auth
def refund(invoice_no: str):
    from plugins.mercado_pago.mercado_pago.models import MercadoPagoPayment
    from vbwd.extensions import db

    payment = (
        db.session.query(MercadoPagoPayment)
        .filter_by(invoice_no=invoice_no)
        .one_or_none()
    )
    if payment is None or not payment.mp_payment_id:
        return jsonify({"error": "not found"}), 404

    body = request.get_json(silent=True) or {}
    amount = body.get("amount")
    if amount is not None:
        try:
            amount = Decimal(str(amount))
        except (ValueError, ArithmeticError):
            return jsonify({"error": "invalid amount"}), 400

    plugin = _get_plugin()
    try:
        adapter = plugin._get_adapter_for_country(payment.country)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    response = adapter.refund_payment(
        payment_intent_id=payment.mp_payment_id, amount=amount
    )
    if not response.success:
        return jsonify({"error": response.error or "MP error"}), 502
    return jsonify({"mp_payment_id": payment.mp_payment_id}), 200
