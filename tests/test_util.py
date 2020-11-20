from binascii import hexlify
import hashlib

from cryptoadvance.specter.util.base58 import (
	double_sha256, encode_base58, encode_base58_checksum,
	decode_base58, BASE58_ALPHABET
	)

from cryptoadvance.specter.util.xpub import (
	hash160, convert_xpub_prefix, get_xpub_fingerprint
	)

def test_wurst(ghost_machine_xpub):
	assert True

### base58 tests

def test_double_sha256():
	testcase = b'specter'
	expected = b'\x80C\x04\x89\xb6Bi7\xf5G\xe7\xc4j5\x02\xcb\xde\xc3\x80>\x12#\xabK\xbaD:\x1a\x15,\xfc\xdd'
	assert double_sha256(testcase) == expected
		
def test_encode_base58_base():
	testcase = b'specter'
	expected = b'5NjEM5pBfP'
	assert encode_base58(testcase) == expected

def test_encode_base58_edge1():
	testcase = b''
	expected = b''
	assert encode_base58(testcase) == expected

def test_encode_base58_edge2():
	testcase = b'%&?'
	expected = b'DUjG'
	assert encode_base58(testcase) == expected

def test_decode_base58_P2SH():
	testcase = '34VDsCMeBjH2AZx4zAn1jYsXDTsMjs2tXD' 
	# Since decode_base58() does not return the checksum, expected is without checksum here
	expected = b'\x05\x1e\xadZ\xcf\xb7\x8f\xfa\xd2\x0bl\xff[\x0c2\x9e\xa0C\xb9\x998'
	assert decode_base58(testcase, strip_leading_zeros=True) == expected

def test_decode_base58_xpub(ghost_machine_xpub):
	testcase = ghost_machine_xpub
	# Since decode_base58() does not return the checksum, expected is without checksum here
	expected = b'\x04\x88\xb2\x1e\x03T\x02\xe6\xa6\x80\x00\x00\x00\xf9\xa9\x0e\x13J\xc8\xf5\x0e\xb8\xddk\xfb\xa9%\x89h\xccg\xfeSh:\x06\xda\xb7T?\x90\x95\xbb\xd7\xde\x036>?\x9f\xdbbx||\xe1\x83\x10%9w\x8a\xc3\xa4\xa0XR\xbc\x1eX\xa0\xf5\xb7\xa8\xc6p\x14\xb9'
	# Strip_leading_zeros argument is not needed here, because we have exactly 82 bytes, thus no 0 bytes
	assert decode_base58(testcase) == expected

def test_encode_base58_checksum_P2SH():
	testcase = decode_base58('34VDsCMeBjH2AZx4zAn1jYsXDTsMjs2tXD', strip_leading_zeros=True)
	expected = '34VDsCMeBjH2AZx4zAn1jYsXDTsMjs2tXD'
	assert encode_base58_checksum(testcase) == expected

def test_encode_base58_checksum_xpub(ghost_machine_xpub):
	testcase = decode_base58(ghost_machine_xpub)
	expected = ghost_machine_xpub
	assert encode_base58_checksum(testcase) == expected

### xpub tests

def test_convert_xpub_prefix(ghost_machine_xpub):
	new_prefix = b"\x04\x9d\x7c\xb2"
	testcase = ghost_machine_xpub
	# No external source found for expected
	expected = 'ypub6X6r7kWWq3jijDins2xMSntWHxNeHn8tWg6LC9k7tTmfSXQ8qtGPwsZ172LXhsupKBZCKdGyMj61LrKhE5zY6wZoACchzV4v7K31QQn2RfD'
	assert convert_xpub_prefix(testcase, new_prefix) == expected


