import datetime
import errno
import json
import logging
import os
import sys

import requests
import urllib3

from cryptoadvance.specter.helpers import is_ip_private
from cryptoadvance.specter.specter_error import SpecterError, handle_exception
from cryptoadvance.specter.rpc import BitcoinRPC
from cryptoadvance.specter.rpc import RpcError as SpecterRpcError
from cryptoadvance.spectrum.spectrum import RPCError as SpectrumRpcError
from cryptoadvance.specter.specter_error import BrokenCoreConnectionException

from cryptoadvance.spectrum.spectrum import Spectrum

from flask import has_app_context

logger = logging.getLogger(__name__)

# TODO: redefine __dir__ and help


class BridgeRPC(BitcoinRPC):
    """A class which behaves like a BitcoinRPC but internally bridges to Spectrum.jsonrpc"""

    def __init__(
        self,
        spectrum,
        app=None,
        wallet_name=None,
    ):
        self.spectrum: Spectrum = spectrum
        self.wallet_name = wallet_name
        self._app = app

    def wallet(self, name=""):
        return type(self)(
            self.spectrum,
            wallet_name=name,
        )

    def clone(self):
        """
        Returns a clone of self.
        Useful if you want to mess with the properties
        """
        return self.__class__(self, self.spectrum, wallet=self.wallet)

    def gettxoutproof(self, *args, **kwargs):
        """Not implemented."""
        raise SpecterError("Using merkle proofs is not supported with Spectrum.")

    def rescanblockchain(self, *args, **kwargs):
        """Not implemented as it's not needed. In order to keep compatibility, we're simply passing"""
        pass

    def multi(self, calls: list, **kwargs):
        """Makes batch request to Core"""
        if self.spectrum is None:
            raise BrokenCoreConnectionException
        type(self).counter += len(calls)
        headers = {"content-type": "application/json"}
        payload = [
            {
                "method": method,
                "params": args if args != [None] else [],
                "jsonrpc": "2.0",
                "id": i,
            }
            for i, (method, *args) in enumerate(calls)
        ]
        timeout = self.timeout
        if "timeout" in kwargs:
            timeout = kwargs["timeout"]

        if kwargs.get("no_wait"):
            # Zero is treated like None, i.e. infinite wait
            timeout = 0.001

        # Spectrum uses a DB and access to it needs an app-context. In order to keep that implementation
        # detail within spectrum, we're establishing a context as needed.
        try:
            if not has_app_context() and self._app is not None:
                with self._app.app_context():
                    result = [
                        self.spectrum.jsonrpc(
                            item, wallet_name=self.wallet_name, catch_exceptions=False
                        )
                        for item in payload
                    ]
            else:
                result = [
                    self.spectrum.jsonrpc(
                        item, wallet_name=self.wallet_name, catch_exceptions=False
                    )
                    for item in payload
                ]
            return result

        except ValueError as ve:
            mock_response = object()
            mock_response.status_code = 500
            mock_response.text = ve
            raise SpecterRpcError(f"Request error: {ve}", mock_response)
        except SpectrumRpcError as se:
            raise SpecterRpcError(
                str(se), status_code=500, error_code=se.code, error_msg=se.message
            )

    def __repr__(self) -> str:
        return f"<BridgeRPC {self.spectrum}>"
