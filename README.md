# Mercado Pago Plugin (Backend)

Mercado Pago — one plugin, 7 LATAM countries (BR, MX, AR, CO, CL, UY,
PE). Covers Pix, Boleto, OXXO, SPEI, PSE, Webpay, PagoEfectivo,
RapiPago, cards with parcelamento/MSI.

## Architecture

One adapter per country (different access-tokens per country app).
The plugin picks the right adapter per request based on
`metadata.country`.

## Configuration (`plugins/config.json`)

```json
{
  "mercado_pago": {
    "sandbox": true,
    "default_country": "BR",
    "countries": {
      "BR": { "enabled": true, "access_token": "…", "webhook_secret": "…" },
      "MX": { "enabled": true, "access_token": "…", "webhook_secret": "…" }
    },
    "max_installments": 12
  }
}
```

## API Routes

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/api/v1/plugins/mercado-pago/preferences` | Bearer | Create preference for a country |
| GET | `/api/v1/plugins/mercado-pago/payments/:invoice/status` | Bearer | Poll payment status |
| POST | `/api/v1/plugins/mercado-pago/webhooks/:country` | HMAC | Country-keyed webhook receiver |
| POST | `/api/v1/plugins/mercado-pago/payments/:invoice/refund` | Admin | Refund (country resolved from record) |

## Database

Owns `mercado_pago_payments` — one row per invoice with country
context so refund + inquiry can route to the right adapter.

## Frontend bundles

- User: [`vbwd-fe-user-plugin-mercado-pago`](https://github.com/VBWD-platform/vbwd-fe-user-plugin-mercado-pago)
- Admin: [`vbwd-fe-admin-plugin-mercado-pago`](https://github.com/VBWD-platform/vbwd-fe-admin-plugin-mercado-pago)

## Testing

```bash
docker compose run --rm test python -m pytest plugins/mercado_pago/tests/ -v
```

## Core requirements

See `docs/dev_log/20260422/sprints/_engineering-requirements.md`.

---

**Core:** [vbwd-backend](https://github.com/VBWD-platform/vbwd-backend)
