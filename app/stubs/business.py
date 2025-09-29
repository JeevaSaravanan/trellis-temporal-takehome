# app/stubs/business.py
from __future__ import annotations

from typing import Dict, Any, Sequence, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.stubs.flaky import flaky_call


def _sum_amount(items: Sequence[Dict[str, Any]]) -> int:
    """Simple demo amount: sum of item qty (int)."""
    return sum(int(i.get("qty", 1)) for i in items or [])


async def order_received(
    session: AsyncSession,
    order_id: str,
    items: Optional[List[Dict[str, Any]]] = None,
    address: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    await flaky_call()

    await session.execute(
        text(
            """
            INSERT INTO orders (id, state, address_json)
            VALUES (:id, 'received', CAST(:addr AS JSONB))
            ON CONFLICT (id) DO UPDATE
              SET updated_at = NOW()
            """
        ),
        {"id": order_id, "addr": address},
    )

    await session.execute(
        text(
            """
            INSERT INTO events(order_id, type, payload_json)
            VALUES (:id, 'order_received', CAST(:payload AS JSONB))
            """
        ),
        {"id": order_id, "payload": {"items": items or [], "address": address or {}}},
    )

    return {"order_id": order_id, "items": items or [], "address": address or {}}


async def order_validated(session: AsyncSession, order: Dict[str, Any]) -> bool:
    await flaky_call()

    if not order.get("items"):
        raise ValueError("No items to validate")

    await session.execute(
        text(
            """
            UPDATE orders
               SET state = 'validated', updated_at = NOW()
             WHERE id = :id
            """
        ),
        {"id": order["order_id"]},
    )

    await session.execute(
        text(
            """
            INSERT INTO events(order_id, type, payload_json)
            VALUES (:id, 'order_validated', '{}')
            """
        ),
        {"id": order["order_id"]},
    )

    return True


async def payment_charged(session: AsyncSession, order: Dict[str, Any], payment_id: str) -> Dict[str, Any]:
    """
    Idempotent payment using payment_id (unique). Safe across retries.
    """
    await flaky_call()

    amount = _sum_amount(order.get("items", []))

    # UPSERT — if payment_id already exists, do nothing (idempotent)
    await session.execute(
        text(
            """
            INSERT INTO payments(payment_id, order_id, amount, status)
            VALUES (:pid, :oid, :amt, 'charged')
            ON CONFLICT (payment_id) DO NOTHING
            """
        ),
        {"pid": payment_id, "oid": order["order_id"], "amt": amount},
    )

    # Read back to confirm record/state
    res = await session.execute(
        text("SELECT payment_id, status, amount FROM payments WHERE payment_id = :pid"),
        {"pid": payment_id},
    )
    row = res.first()
    if not row:
        # Defensive: should not happen with the simple demo logic
        raise RuntimeError("Payment record missing after insert attempt")

    await session.execute(
        text(
            """
            INSERT INTO events(order_id, type, payload_json)
            VALUES (:id, 'payment_charged', CAST(:payload AS JSONB))
            """
        ),
        {
            "id": order["order_id"],
            "payload": {
                "payment_id": payment_id,
                "amount": int(row.amount),
                "status": row.status,
            },
        },
    )

    return {"status": row.status, "amount": int(row.amount), "payment_id": row.payment_id}


async def order_shipped(session: AsyncSession, order: Dict[str, Any]) -> str:
    await flaky_call()

    await session.execute(
        text(
            """
            UPDATE orders
               SET state = 'shipped', updated_at = NOW()
             WHERE id = :id
            """
        ),
        {"id": order["order_id"]},
    )

    await session.execute(
        text(
            """
            INSERT INTO events(order_id, type, payload_json)
            VALUES (:id, 'order_shipped', '{}')
            """
        ),
        {"id": order["order_id"]},
    )

    return "Shipped"


async def package_prepared(session: AsyncSession, order: Dict[str, Any]) -> str:
    await flaky_call()

    await session.execute(
        text(
            """
            INSERT INTO events(order_id, type, payload_json)
            VALUES (:id, 'package_prepared', '{}')
            """
        ),
        {"id": order["order_id"]},
    )

    return "Package ready"


async def carrier_dispatched(session: AsyncSession, order: Dict[str, Any]) -> str:
    await flaky_call()

    await session.execute(
        text(
            """
            INSERT INTO events(order_id, type, payload_json)
            VALUES (:id, 'carrier_dispatched', '{}')
            """
        ),
        {"id": order["order_id"]},
    )

    return "Dispatched"
