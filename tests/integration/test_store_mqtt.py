# Manta Python
# Manta Protocol Implementation for Python
# Copyright (C) 2018-2019 Alessandro Viganò
from decimal import Decimal

import pytest
import requests

from manta.messages import Status
from manta.store import Store

# logging.basicConfig(level=logging.INFO)


@pytest.fixture
def store(test_containers) -> Store:
    return Store(
        "device1",
        host=test_containers.mosquitto_host,
        port=int(test_containers.mosquitto_port),
    )


@pytest.mark.timeout(5)
@pytest.mark.asyncio
async def test_connect(store):
    await store.connect()
    store.close()


@pytest.mark.timeout(2)
@pytest.mark.asyncio
async def test_generate_payment_request(store):
    # noinspection PyUnresolvedReferences
    ack = await store.merchant_order_request(amount=Decimal(10), fiat="eur")
    assert ack.url.startswith("manta://")


# noinspection PyUnresolvedReferences
@pytest.mark.timeout(5)
@pytest.mark.asyncio
async def test_ack(store, test_containers):

    ack = await store.merchant_order_request(amount=Decimal(10), fiat="eur")
    requests.post(test_containers.wallet_url + "/scan", json={"url": ack.url})

    ack_message = await store.acks.get()

    assert Status.PENDING == ack_message.status


@pytest.mark.timeout(5)
@pytest.mark.asyncio
# noinspection PyUnresolvedReferences
async def test_ack_paid(store, test_containers):
    await test_ack(store, test_containers)

    requests.post(
        test_containers.pp_url + "/confirm", json={"session_id": store.session_id}
    )

    ack_message = await store.acks.get()

    assert Status.PAID == ack_message.status
