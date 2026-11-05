import unittest

from cryptoadvance.specter.helpers import der_to_bytes


class TestDerToBytes(unittest.TestCase):
    def test_underscore_is_rejected(self):
        with self.assertRaises(ValueError):
            der_to_bytes("m/1_0")

    def test_plain_index(self):
        self.assertEqual(der_to_bytes("m/10"), (10).to_bytes(4, "little"))

    def test_hardened_index(self):
        self.assertEqual(
            der_to_bytes("m/1h"), (0x80000001).to_bytes(4, "little")
        )


if __name__ == "__main__":
    unittest.main()
