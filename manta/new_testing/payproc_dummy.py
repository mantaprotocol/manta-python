import json
import logging
import os
from functools import partial

import attr
import cattr
from decimal import Decimal
from typing import Optional, List

import typer
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

from manta.messages import Destination, Merchant, MerchantOrderRequestMessage
from manta.payproc import PayProc

logger = logging.getLogger(__name__)
app = FastAPI()

pp: Optional[PayProc]

cattr.register_unstructure_hook(Decimal, lambda d: str(d))
cattr.register_structure_hook(Decimal, lambda d, t: Decimal(d))

# language=JSON
DESTINATIONS = """
    [
        {
            "amount": "10.5",
            "destination_address": "xrb_3d1ab61eswzsgx5arwqc3gw8xjcsxd7a5egtr69jixa5it9yu9fzct9nyjyx",
            "crypto_currency": "NANO"
        }
    ]
"""

# language=JSON
SUPPORTED_CRYPTOS = """
    ["btc", "xmr", "nano"]
"""

# language=JSON
MERCHANT = """
    {
        "name": "Merchant 1",
        "address": "5th Avenue"
    }
"""


class ConfirmationRequest(BaseModel):
    session_id: str


def _get_destinations(
    destinations: List[Destination],
    application_id,
    merchant_order: MerchantOrderRequestMessage,
):
    if merchant_order.crypto_currency:
        destination = next(
            x
            for x in destinations
            if x.crypto_currency == merchant_order.crypto_currency
        )
        return [destination]
    else:
        return destinations


@app.on_event("startup")
def startup_event():
    global pp

    logger.info("Startup event")

    pp = PayProc(
        os.environ["PP_KEYFILE"],
        cert_file=os.environ["PP_CERTFILE"] if os.environ["PP_CERTFILE"] else None,
        host=os.environ["BROKER_HOST"],
        port=int(os.environ["BROKER_PORT"]),
    )

    merchant = Merchant.from_json(os.environ["PP_MERCHANT"])
    destinations = cattr.structure(
        json.loads(os.environ["PP_DESTINATIONS"]), List[Destination]
    )
    supported_cryptos = cattr.structure(
        json.loads(os.environ["PP_SUPPORTED_CRYPTOS"]), List[str]
    )

    pp.get_merchant = lambda x: merchant
    pp.get_destinations = partial(_get_destinations, destinations)
    pp.get_supported_cryptos = lambda device, payment_request: supported_cryptos

    logger.info(
        f"Starting payproc with broker {os.environ['BROKER_HOST']}"
        f":{os.environ['BROKER_PORT']}"
    )

    pp.run()


@app.post("/confirm/", response_model=str)
async def confirm(request: ConfirmationRequest):
    logger.info("Got confirm request")
    pp.confirm(request.session_id)

    return "ok"


@app.get("/healthcheck", response_model=str)
async def healthcheck():
    return "ok"


def main(
    host: str = typer.Option("127.0.0.1", envvar="PP_HOST", show_envvar=True),
    port: int = typer.Option(8081, envvar="PP_PORT", show_envvar=True),
    reload: bool = typer.Option(False, envvar="PP_RELOAD", show_envvar=True),
    broker_host: str = typer.Option(
        "127.0.0.1", envvar="BROKER_HOST", show_envvar=True
    ),
    broker_port: int = typer.Option(1883, envvar="BROKER_PORT", show_envvar=True),
    keyfile: str = typer.Option(..., envvar="PP_KEYFILE", show_envvar=True),
    certfile: str = typer.Option("", envvar="PP_CERTFILE", show_envvar=True),
    merchant: str = typer.Option(MERCHANT, envvar="PP_MERCHANT", show_envvar=True),
    destinations: str = typer.Option(
        DESTINATIONS, envvar="PP_DESTINATIONS", show_envvar=True
    ),
    supported_cryptos: str = typer.Option(
        SUPPORTED_CRYPTOS, envvar="PP_CRYPTOS", show_envvar=True
    ),
):
    logging.basicConfig(level=logging.INFO)

    os.environ["PP_KEYFILE"] = keyfile
    os.environ["PP_CERTFILE"] = certfile
    os.environ["BROKER_HOST"] = broker_host
    os.environ["BROKER_PORT"] = str(broker_port)
    os.environ["PP_MERCHANT"] = merchant
    os.environ["PP_DESTINATIONS"] = destinations
    os.environ["PP_SUPPORTED_CRYPTOS"] = supported_cryptos

    logger.info(f"Starting payproc_dummy on {host}:{port}")

    uvicorn.run(
        "manta.new_testing.payproc_dummy:app", host=host, port=port, reload=reload
    )


def run():
    typer.run(main)


if __name__ == "__main__":
    run()
