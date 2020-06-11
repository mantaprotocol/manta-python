# Manta Python
# Manta Protocol Implementation for Python
# Copyright (C) 2018-2019 Alessandro Viganò

import os
import pathlib
import pytest
from attr import dataclass
from testcontainers.compose import DockerCompose

pytest.register_assert_rewrite("tests.utils")

# it's a fixture used in the tests
from .utils import mock_mqtt  # noqa E402


@pytest.fixture(scope="session")
def tests_dir():
    return pathlib.Path(os.path.dirname(os.path.realpath(__file__)))


@dataclass
class ContainersParameters:
    mosquitto_port: int = 1883
    mosquitto_host: str = "localhost"
    wallet_port: int = 8082
    wallet_host: str = "localhost"
    store_port: int = 8080
    store_host: str = "localhost"
    pp_port: int = 8081
    pp_host: str = "localhost"

    @property
    def store_url(self):
        return f"http://{self.store_host}:{self.store_port}"

    @property
    def wallet_url(self):
        return f"http://{self.wallet_host}:{self.wallet_port}"

    @property
    def pp_url(self):
        return f"http://{self.pp_host}:{self.pp_port}"


@pytest.fixture(scope="session")
def test_containers():
    # hostname = socket.gethostname()
    # ip_address = socket.gethostbyname(hostname)
    # os.environ["BROKER_HOST"] = ip_address

    with DockerCompose(".") as compose:
        params = ContainersParameters(
            wallet_port=compose.get_service_port("wallet", 8082),
            store_port=compose.get_service_port("store", 8080),
            mosquitto_port=compose.get_service_port("mosquitto", 1883),
            pp_port=compose.get_service_port("payproc", 8081)
            # mosquitto_host=compose.get_service_host("mosquitto", 1883)
        )

        yield params
