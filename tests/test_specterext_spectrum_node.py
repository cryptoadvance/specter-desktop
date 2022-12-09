import logging
import pytest
from cryptoadvance.specterext.spectrum.spectrum_node import SpectrumNode
from cryptoadvance.spectrum.util import SpectrumException
from cryptoadvance.specter.specter_error import BrokenCoreConnectionException
from cryptoadvance.specter.persistence import PersistentObject


def test_SpectrumNode(caplog):
    caplog.set_level(logging.DEBUG)

    # Instantiate directly:
    sn = SpectrumNode("Some name")
    # An AbstractNode return None if the connection is broken for:
    assert sn.chain == None
    # Empty dict for info:
    assert sn.info == {}
    assert sn.network_info == {"subversion": "", "version": 999999}
    assert sn.bitcoin_core_version_raw == 99999
    assert sn.is_running == False
    assert (
        type(sn.network_parameters) == dict
    )  # a huge dict {'Yprv': b'\x02B\x85\xb5', 'Ypub': b'\x02B\x89\xef',  ...}
    with pytest.raises(BrokenCoreConnectionException):
        sn.uptime()

    a_dict = {
        "python_class": "cryptoadvance.specterext.spectrum.spectrum_node.SpectrumNode",
        "name": "Spectrum Node",
        "alias": "spectrum_node",
        "host": "kirsche.emzy.de",
        "port": 5002,
        "ssl": True,
    }

    # Instantiate via PersistentObject:
    sn = PersistentObject.from_json(a_dict)

    assert type(sn) == SpectrumNode
    assert sn.host == "kirsche.emzy.de"
    assert sn.port == 5002
    assert sn.ssl == True
