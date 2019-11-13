''' Tests for lovac.models '''
import shutil
import pytest
from specter import Specter, alias

@pytest.fixture
def specter_not_configured():
    # Make sure that this folder never ever gets a reasonable non-testing use-case
    data_folder = './test_specter_data_2789334'
    shutil.rmtree(data_folder, ignore_errors=True) 
    yield Specter(data_folder=data_folder)    
    shutil.rmtree(data_folder, ignore_errors=True)


def test_alias():
    assert alias("wurst 1") == "wurst_1"
    assert alias("wurst_1") == "wurst_1"
    assert alias("Wurst$ 1") == "wurst_1"

def test_specter_permrights():
    with pytest.raises(Exception):
        Specter("/notexisting_directory")

def test_specter(specter_not_configured):
    specter_not_configured.check()
    assert specter_not_configured.wallets is not None
    assert specter_not_configured.devices is not None
    some_json = specter_not_configured.test_rpc()
    assert some_json["out"] == ""
    assert some_json["err"] == "autodetect failed"