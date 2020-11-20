import pytest

@pytest.fixture
def ghost_machine_xpub():
	""" Using https://iancoleman.io/bip39/ """
	bip39 = 'ghost ghost ghost ghost ghost ghost ghost ghost ghost ghost ghost machine'
	seed = 'e918ed16aa5c5753ea30485394d0f1722e8baa2c9dd54c42a48ee7aede218eb7821a7bb25e2ac0e40e2c474d56e26e2c3cf903ec9ae8b6a4d0de982dbe0ed5ef'
	root_key = 'xprv9s21ZrQH143K3cTKa3Bs6BJHTe9CrpeynNGA5z4SMsqMawSmfvfv4z8JChkbHgM8BWzvUxMACHTE3NwihzPZRcdQcJ4N7FTbj52UdsxkMDh'
	# BIP 44
	xpub = 'xpub6CGap5qbgNCEsvXg2gAjEho17zECMA9PbZa7QkrEWTPnPRaubE6qKots5pNwhyFtuYSPa9gQu4jTTZi8WPaXJhtCHrvHQaFRqayN1saQoWv'
	return xpub
