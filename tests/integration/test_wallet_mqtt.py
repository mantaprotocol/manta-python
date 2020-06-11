# Manta Python
# Manta Protocol Implementation for Python
# Copyright (C) 2018-2019 Alessandro Viganò

import asyncio
import os
import socket
from dataclasses import dataclass
from decimal import Decimal
import logging

import pytest
import requests
from testcontainers.compose import DockerCompose

from manta.messages import PaymentRequestEnvelope, Status
from manta.wallet import Wallet

logging.basicConfig(level=logging.INFO)


@pytest.mark.incremental
class TestWallet:
    @pytest.mark.timeout(2)
    @pytest.mark.asyncio
    async def test_connect(self, test_containers):
        wallet = Wallet.factory(
            f"manta://localhost:{test_containers.mosquitto_port}/123"
        )
        await wallet.connect()
        wallet.close()

    @pytest.mark.asyncio
    async def test_get_payment_request(self, test_containers):

        r = requests.post(
            f"{test_containers.store_url}/merchant_order",
            json={"amount": "10", "fiat": "EUR"},
        )
        logging.info(r)
        ack_message = r.json()
        url: str = ack_message["url"]

        logging.info(url)

        # Replace mosquitto address to localhost
        url = url.replace("mosquitto", f"localhost:{test_containers.mosquitto_port}")

        wallet = Wallet.factory(url)

        envelope = await wallet.get_payment_request("NANO")
        self.pr = envelope.unpack()

        assert 10 == self.pr.amount
        assert "EUR" == self.pr.fiat_currency
        return wallet

    @pytest.mark.asyncio
    async def test_send_payment(self, test_containers):
        # noinspection PyUnresolvedReferences

        wallet = await self.test_get_payment_request(test_containers)

        await wallet.send_payment(crypto_currency="NANO", transaction_hash="myhash")

        ack = await wallet.acks.get()

        assert Status.PENDING == ack.status
        return wallet

    @pytest.mark.asyncio
    async def test_ack_on_confirmation(self, test_containers):
        # noinspection PyUnresolvedReferences
        wallet = await self.test_send_payment(test_containers)

        requests.post(
            test_containers.pp_url + "/confirm", json={"session_id": wallet.session_id}
        )

        ack = await wallet.acks.get()

        assert Status.PAID == ack.status
