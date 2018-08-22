from __future__ import annotations

import paho.mqtt.client as mqtt
import asyncio
import logging
import threading
import simplejson as json
import base64, uuid

from typing import Callable


from manta.messages import MerchantOrderReplyMessage, MerchantOrderRequestMessage, AckMessage

logger = logging.getLogger(__name__)


def generate_session_id() -> str:
    return base64.b64encode(uuid.uuid4().bytes, b"-_").decode("utf-8")
    # The following is more secure
    # return base64.b64encode(M2Crypto.m2.rand_bytes(num_bytes))


def wrap_callback(f):
    def wrapper(self: Store, *args):
        self.loop.call_soon_threadsafe(f, self, *args)

    return wrapper


class Store:
    mqtt_client: mqtt.Client
    loop: asyncio.AbstractEventLoop
    connected: asyncio.Event
    generate_payment_future: asyncio.Future = None
    device_id: str
    session_id: str = None
    acks = asyncio.Queue
    first_connect = False

    def __init__(self, device_id: str):
        self.device_id = device_id
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.on_disconnect = self.on_disconnect
        try:
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        self.acks = asyncio.Queue(loop=self.loop)
        self.connected = asyncio.Event(loop=self.loop)

    def close(self):
        self.mqtt_client.disconnect()
        self.mqtt_client.loop_stop()

    @wrap_callback
    def on_disconnect(self, client, userdata, rc):
        self.connected.clear()

    @wrap_callback
    def on_connect(self, client, userdata, flags, rc):
        logger.info("Connected")
        self.connected.set()

    @wrap_callback
    def on_message(self, client: mqtt.Client, userdata, msg):
        logger.info("Got {} on {}".format(msg.payload, msg.topic))
        tokens = msg.topic.split('/')

        if tokens[0] == 'generate_payment_request':
            decoded = json.loads(msg.payload)
            reply = MerchantOrderReplyMessage(**decoded)

            if reply.status == 200:
                self.mqtt_client.subscribe("acks/{}".format(self.session_id))
                self.loop.call_soon_threadsafe(self.generate_payment_future.set_result, reply.url)
            else:
                self.loop.call_soon_threadsafe(self.generate_payment_future.set_exception, Exception(reply.status))
        elif tokens[0] == 'acks':
            session_id = tokens[1]
            logger.info("Got ack message")
            ack = AckMessage.from_json(msg.payload)
            self.acks.put_nowait(ack)

    async def connect(self):
        if not self.first_connect:
            self.mqtt_client.connect("localhost")
            self.mqtt_client.loop_start()
            self.first_connect = True

        await self.connected.wait()

    # def generate_payment_request(self, amount: float, fiat: str, crypto: str = None):
    #     return self.loop.run_until_complete(self.__generate_payment_request(amount, fiat, crypto))

    async def merchant_order_request(self, amount: float, fiat: str, crypto: str = None):
        await self.connect()
        self.session_id = generate_session_id()
        request = MerchantOrderRequestMessage(
            amount=amount,
            session_id=self.session_id,
            fiat_currency=fiat,
            crypto_currency=crypto
        )
        self.generate_payment_future = self.loop.create_future()
        self.mqtt_client.subscribe("generate_payment_request/{}/reply".format(self.device_id))
        self.mqtt_client.publish("generate_payment_request/{}/request".format(self.device_id),
                                 request.to_json())

        logger.info("Publishing generate_payment_request")

        result = await asyncio.wait_for(self.generate_payment_future, 3)

        return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    store = Store("device1")
    store.merchant_order_request()
