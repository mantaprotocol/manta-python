import pytest
import requests

from manta.messages import Status
from manta.store import Store

# logging.basicConfig(level=logging.INFO)

PP_HOST = "http://localhost:8081"
WALLET_HOST = "http://localhost:8082"


@pytest.fixture
async def store() -> Store:
    return Store('device1')


@pytest.mark.timeout(2)
@pytest.mark.asyncio
async def test_connect(store):
    # noinspection PyUnresolvedReferences
    await store.connect()
    store.close()


@pytest.mark.timeout(2)
@pytest.mark.asyncio
async def test_generate_payment_request(store):
    # noinspection PyUnresolvedReferences
    ack = await store.merchant_order_request(amount=10, fiat='eur')
    assert ack.url.startswith("manta://")


# noinspection PyUnresolvedReferences
@pytest.mark.timeout(5)
@pytest.mark.asyncio
async def test_ack(store):

    ack = await store.merchant_order_request(amount=10, fiat='eur')

    requests.post(WALLET_HOST + "/scan", json={"url": ack.url})

    ack_message = await store.acks.get()

    assert Status.PENDING == ack_message.status


@pytest.mark.timeout(5)
@pytest.mark.asyncio
# noinspection PyUnresolvedReferences
async def test_ack_paid(store):
    await test_ack(store)

    requests.post(PP_HOST + "/confirm",
                  json={'session_id': store.session_id})

    ack_message = await store.acks.get()

    assert Status.PAID == ack_message.status