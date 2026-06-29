import asyncio

from fastapi import APIRouter
from lnbits.tasks import create_permanent_unique_task
from loguru import logger

from .crud import db
from .tasks import run_scheduler_loop, wait_for_paid_invoices
from .views import market_town_generic_router
from .views_api import market_town_api_router

market_town_ext: APIRouter = APIRouter(prefix="/market_town", tags=["Market Town"])
market_town_ext.include_router(market_town_generic_router)
market_town_ext.include_router(market_town_api_router)


market_town_static_files = [
    {
        "path": "/market_town/static",
        "name": "market_town_static",
    }
]

scheduled_tasks: list[asyncio.Task] = []


def market_town_stop():
    for task in scheduled_tasks:
        try:
            task.cancel()
        except Exception as ex:
            logger.warning(ex)


def market_town_start():
    scheduled_tasks.append(create_permanent_unique_task("ext_market_town_paid_invoices", wait_for_paid_invoices))
    scheduled_tasks.append(create_permanent_unique_task("ext_market_town_scheduler", run_scheduler_loop))


__all__ = [
    "db",
    "market_town_ext",
    "market_town_start",
    "market_town_static_files",
    "market_town_stop",
]
