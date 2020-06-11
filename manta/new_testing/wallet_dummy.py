# Manta Python
# Manta Protocol Implementation for Python
# Copyright (C) 2018-2019 Alessandro Viganò

import asyncio
import logging
import sys
from concurrent.futures._base import TimeoutError

import inquirer
import nano
import typer
import uvicorn
from cryptography.x509 import NameOID
from fastapi import FastAPI
from pydantic import BaseModel

from manta.messages import verify_chain, PaymentRequestEnvelope
from manta.wallet import Wallet

ONCE = False

logger = logging.getLogger(__name__)
app = FastAPI()


class ScanRequest(BaseModel):
    url: str


def query_yes_no(question, default="yes"):
    """Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).

    The "answer" return value is True for "yes" or False for "no".
    """
    valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = input().lower()
        if default is not None and choice == "":
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' " "(or 'y' or 'n').\n")


async def get_payment_request(
    wallet: Wallet, crypto_currency: str = "all"
) -> PaymentRequestEnvelope:
    try:
        envelope = await wallet.get_payment_request(crypto_currency)
    except TimeoutError as e:
        if ONCE:
            print("Timeout exception in waiting for payment")
            sys.exit(1)
        else:
            raise e

    return envelope


def verify_envelope(
    envelope: PaymentRequestEnvelope, certificate, ca_certificate
) -> bool:
    verified = False

    if ca_certificate:
        path = verify_chain(certificate, ca_certificate)

        if path:
            if envelope.verify(certificate):
                verified = True
                logger.info("Verified Request")
                logger.info(
                    "Certificate issued to {}".format(
                        certificate.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[
                            0
                        ].value
                    )
                )
            else:
                logger.error("Invalid Signature")
        else:
            logger.error("Invalid Certification Path")

    return verified


async def get_payment(
    url: str,
    testing: bool = False,
    nano_wallet: str = None,
    account: str = None,
    ca_certificate: str = None,
):
    wallet = Wallet.factory(url)

    envelope = await get_payment_request(wallet)

    verified = False
    certificate = None

    if ca_certificate:
        certificate = await wallet.get_certificate()

        verified = verify_envelope(envelope, certificate, ca_certificate)

    pr = envelope.unpack()

    logger.info("Payment request: {}".format(pr))

    options = [x for x in pr.supported_cryptos]

    questions = [
        inquirer.List(
            "crypto", message=" What crypto you want to pay with?", choices=options
        )
    ]

    if not testing:
        answers = inquirer.prompt(questions)

        chosen_crypto = answers["crypto"]

        # Check if we have already the destination
        destination = pr.get_destination(chosen_crypto)

        # Otherwise ask payment provider
        if not destination:
            logger.info("Requesting payment request for {}".format(chosen_crypto))
            envelope = await get_payment_request(wallet, chosen_crypto)
            verified = False

            if ca_certificate:
                verified = verify_envelope(envelope, certificate, ca_certificate)

            pr = envelope.unpack()
            logger.info("Payment request: {}".format(pr))

            destination = pr.get_destination(chosen_crypto)

        if answers["crypto"] == "NANO":
            rpc = nano.rpc.Client(host="http://localhost:7076")
            balance = rpc.account_balance(account=account)
            print()
            print(
                "Actual balance: {}".format(
                    str(
                        nano.convert(
                            from_unit="raw", to_unit="XRB", value=balance["balance"]
                        )
                    )
                )
            )

            if not verified:
                print("WARNING!!!! THIS IS NOT VERIFIED REQUEST")

            destination = pr.get_destination("NANO")

            if query_yes_no(
                f"Pay {destination.amount} {destination.crypto_currency} "
                f"({pr.amount} {pr.fiat_currency}) to {pr.merchant}"
            ):
                amount = int(
                    nano.convert(
                        from_unit="XRB", to_unit="raw", value=destination.amount
                    )
                )

                print(amount)

                block = rpc.send(
                    wallet=nano_wallet,
                    source=account,
                    destination=destination.destination_address,
                    amount=amount,
                )

                await wallet.send_payment(
                    transaction_hash=block, crypto_currency="NANO"
                )
        elif answers["crypto"] == "TESTCOIN":
            await wallet.send_payment(
                transaction_hash="test_hash", crypto_currency="TESTCOIN"
            )
        else:
            print("Not supported!")
            sys.exit()

    else:
        await wallet.send_payment("myhash", pr.destinations[0].crypto_currency)

    ack = await wallet.acks.get()
    print(ack)


@app.post("/scan/", response_model=str)
async def scan(request: ScanRequest):
    logger.info(f"Got scan request for {request.url}")
    await get_payment(request.url, testing=True)

    return "ok"


def main(
    host: str = typer.Option("127.0.0.1", envvar="WALLET_HOST", show_envvar=True),
    port: int = typer.Option(8082, envvar="WALLET_PORT", show_envvar=True),
    reload: bool = typer.Option(False, envvar="STORE_RELOAD", show_envvar=True),
    url: str = typer.Argument(None),
    testing: bool = typer.Option(False, "--testing", envvar="WALLET_TESTING"),
    wallet: str = typer.Option(None, envvar="WALLET_NANO_WALLET"),
    account: str = typer.Option(None, envvar="WALLET_NANO_ACCOUNT"),
    certificate: str = typer.Option(None, envvar="WALLET_CERTIFICATE"),
):
    global ONCE, loop

    logging.basicConfig(level=logging.INFO)

    if len([x for x in (wallet, account) if x is not None]) == 1:
        raise typer.BadParameter("--wallet and --account must be given together")

    if not testing and url is None:
        raise typer.BadParameter("URL must specified while not in testing mode")

    if not testing:
        ONCE = True
        loop = asyncio.get_event_loop()

        loop.run_until_complete(
            get_payment(
                url=url,
                testing=testing,
                nano_wallet=wallet,
                account=account,
                ca_certificate=certificate,
            )
        )
    else:
        logger.info("Starting wallet_dummy")
        uvicorn.run(
            "manta.new_testing.wallet_dummy:app", host=host, port=port, reload=reload
        )


def run():
    typer.run(main)


if __name__ == "__main__":
    run()
