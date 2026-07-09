import asyncio

from lnbits.core.models import Payment
from lnbits.tasks import register_invoice_listener
from loguru import logger

from .services import maybe_resolve_due_epochs, payment_received_for_claim, payment_received_for_sponsorship


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, "ext_market_town")
    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    tag = payment.extra.get("tag")
    if tag not in {"market_town", "market_town_sponsorship"}:
        return

    logger.info(f"Invoice paid for {tag}: {payment.payment_hash}")
    try:
        if tag == "market_town_sponsorship":
            await payment_received_for_sponsorship(payment)
        else:
            await payment_received_for_claim(payment)
    except Exception as exc:
        logger.error(f"Error processing Market Town payment: {exc}")


async def run_scheduler_loop():
    while True:
        try:
            await maybe_resolve_due_epochs()
        except Exception as exc:
            logger.warning(f"Market Town scheduler error: {exc}")
        await asyncio.sleep(15)
