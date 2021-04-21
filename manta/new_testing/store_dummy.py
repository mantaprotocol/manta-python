# Manta Python
# Manta Protocol Implementation for Python
# Copyright (C) 2018-2019 Alessandro Viganò
import asyncio
import os
from asyncio import Task
from decimal import Decimal
import logging
import traceback
from typing import Optional, Dict, Any, Type, get_type_hints

import typer
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from starlette.background import BackgroundTasks

import manta.new_testing.messages_pyd as pyd
from manta.messages import AckMessage, Status
from manta.new_testing.pyd_decimal_config import DecimalConfig

from manta.store import Store

logger = logging.getLogger(__name__)
app = FastAPI()
store: Optional[Store] = None
status: Optional[Status] = None
update_task: Optional[Task] = None

# store = Store("dummy_store")


class OrderRequest(BaseModel):
    amount: Decimal
    fiat: str
    crypto: Optional[str] = None

    class Config(DecimalConfig):
        pass


class StatusResponse(BaseModel):
    status: Optional[Status]


async def update_status():
    global store, status

    while True:
        status = (await store.acks.get()).status
        logger.info(f"Updating status to {status}")


@app.on_event("startup")
def startup_event():
    global store
    store = Store(
        device_id="store_dummy",
        host=os.environ["BROKER_HOST"],
        port=int(os.environ["BROKER_PORT"]),
    )


@app.post("/merchant_order/", response_model=pyd.AckMessage)
async def merchant_order(order: OrderRequest):
    global update_task, status

    logger.info(f"New order: {order}")

    status = None

    if update_task is not None:
        logger.info("Cancelling update task")
        update_task.cancel()

    reply = await store.merchant_order_request(**order.dict())

    update_task = asyncio.create_task(update_status())

    return reply.unstructure()


@app.get("/status/", response_model=StatusResponse)
def get_status():
    return StatusResponse(status=status)


@app.get("/healthcheck", response_model=str)
async def healthcheck():
    return "ok"


def main(
    host: str = typer.Option("127.0.0.1", envvar="STORE_HOST", show_envvar=True),
    port: int = typer.Option(8080, envvar="STORE_PORT", show_envvar=True),
    reload: bool = typer.Option(False, envvar="STORE_RELOAD", show_envvar=True),
    broker_host: str = typer.Option(
        "127.0.0.1", envvar="BROKER_HOST", show_envvar=True
    ),
    broker_port: int = typer.Option(1883, envvar="BROKER_PORT", show_envvar=True),
):
    global store
    logging.basicConfig(level=logging.INFO)
    # print (OrderRequest.schema_json())

    logger.info(f"Starting store_dummy with broker {broker_host}: {broker_port}")

    os.environ["BROKER_HOST"] = broker_host
    os.environ["BROKER_PORT"] = str(broker_port)

    uvicorn.run(
        "manta.new_testing.store_dummy:app", host=host, port=port, reload=reload
    )


def run():
    typer.run(main)


if __name__ == "__main__":
    run()
