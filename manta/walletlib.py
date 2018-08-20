import asyncio
import logging
import re
from typing import Optional, Any

import paho.mqtt.client as mqtt

from manta.messages import PaymentRequestMessage, PaymentRequestEnvelope
from certvalidator import CertificateValidator

logger = logging.getLogger(__name__)


class Wallet:
    mqtt_client: mqtt.Client
    loop: asyncio.AbstractEventLoop
    connected: bool = False
    host: str
    port: int
    session_id: str
    payment_request_future: asyncio.Future = None
    connect_future: asyncio.Future = None

    @classmethod
    def factory(cls, url:str, certificate:str):
        match = cls.parse_url(url)
        if match:
            port = 1883 if match[2] is None else int(match[2])
            return cls(url, match[3], host=match[1], port=port)
        else:
            return None

    def __init__(self, url:str,  session_id:str, host:str="localhost", port:int=1883):
        self.host = host
        self.port = port
        self.session_id = session_id

        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.on_disconnect = self.on_disconnect

        try:
            self.loop = asyncio.get_event_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        self.mqtt_client.loop_start()

    def close(self):
        self.mqtt_client.disconnect()
        self.mqtt_client.loop_stop()

    def on_disconnect(self, client, userdata, rc):
        self.connected = False

    def on_connect(self, client, userdata, flags, rc):
        logger.info("Connected")
        self.connected = True
        self.loop.call_soon_threadsafe(self.connect_future.set_result, None)

    def on_message(self, client: mqtt.Client, userdata, msg):
        logger.info("Got {} on {}".format(msg.payload, msg.topic))
        tokens = msg.topic.split('/')

        if tokens[0] == "payment_requests":
            envelope = PaymentRequestEnvelope.from_json(msg.payload)
            self.loop.call_soon_threadsafe(self.payment_request_future.set_result, envelope)

    async def connect(self):
        if self.connected:
            return

        if self.connect_future is None:
            self.connect_future = self.loop.create_future()
            self.mqtt_client.connect(self.host, port=self.port)

            if self.connect_future.done():
                self.connect_future = self.loop.create_future()

            await self.connect_future

    @staticmethod
    def parse_url(url:str) -> Optional[re.Match]:
        pattern = "^manta:\\/\\/((?:\\w|\\.)+)(?::(\\d+))?\\/(\\d+)$"
        return re.match(pattern, url)

    async def __get_payment_request(self, crypto_currency:str) -> PaymentRequestEnvelope:
        await self.connect()

        self.payment_request_future = self.loop.create_future()
        self.mqtt_client.subscribe("payment_requests/{}".format(self.session_id))
        self.mqtt_client.publish("payment_requests/{}/{}".format(self.session_id, crypto_currency))

        result = await asyncio.wait_for(self.payment_request_future, 3)
        return result

    def get_payment_request(self, crypto_currency:str) -> PaymentRequestEnvelope:
        return self.loop.run_until_complete(self.__get_payment_request(crypto_currency))