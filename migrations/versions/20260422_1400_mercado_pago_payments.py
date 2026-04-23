"""Create mercado_pago_payments table.

Revision ID: 20260422_1400_mp
Revises: 20260422_1300_truemoney
Create Date: 2026-04-22

Sprint 33 — Mercado Pago LATAM plugin.
"""
from alembic import op
import sqlalchemy as sa


revision = "20260422_1400_mp"
down_revision = "20260422_1300_truemoney"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mercado_pago_payments",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("invoice_no", sa.String(length=64), nullable=False, unique=True),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("preference_id", sa.String(length=128), nullable=True),
        sa.Column("mp_payment_id", sa.String(length=128), nullable=True),
        sa.Column("method", sa.String(length=32), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("installments", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("last_provider_status", sa.String(length=32), nullable=True),
        sa.Column("extra_data", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_mp_payments_country",
        "mercado_pago_payments",
        ["country"],
        unique=False,
    )
    op.create_index(
        "ix_mp_payments_mp_payment_id",
        "mercado_pago_payments",
        ["mp_payment_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_mp_payments_mp_payment_id", table_name="mercado_pago_payments"
    )
    op.drop_index(
        "ix_mp_payments_country", table_name="mercado_pago_payments"
    )
    op.drop_table("mercado_pago_payments")
