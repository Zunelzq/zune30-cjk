"""Regression test: rebuild a captured MTPZ application certificate message."""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from zunesync import mtpz  # noqa: E402

KEYS_BE = Path(r"E:\zune_cjk\.mtpz-data.be")
KEYS_BAD = Path(r"E:\zune_cjk\.mtpz-data")
CAPTURE = Path(r"E:\zune_cjk\coldstart-blobs\out_op9212_tx341.bin")


class MtpzTests(unittest.TestCase):
    @unittest.skipUnless(KEYS_BE.exists(), "no .mtpz-data.be")
    def test_keyset_is_consistent(self):
        keys = mtpz.load_keys(str(KEYS_BE))
        self.assertTrue(mtpz.verify_keyset(keys))

    @unittest.skipUnless(KEYS_BAD.exists(), "no .mtpz-data")
    def test_base_keyset_is_broken(self):
        # Documents why the first MTPZ attempt failed.
        keys = mtpz.load_keys(str(KEYS_BAD))
        self.assertFalse(mtpz.verify_keyset(keys))

    @unittest.skipUnless(KEYS_BE.exists() and CAPTURE.exists(), "no capture")
    def test_signature_matches_capture(self):
        keys = mtpz.load_keys(str(KEYS_BE))
        acm = CAPTURE.read_bytes()
        self.assertEqual(len(acm), 785)
        self.assertTrue(mtpz.verify_acm(acm, keys))

    @unittest.skipUnless(KEYS_BE.exists(), "no .mtpz-data.be")
    def test_roundtrip_with_fresh_random(self):
        keys = mtpz.load_keys(str(KEYS_BE))
        certs = keys["certificates"]
        # the capture carries 629 bytes; pad our 620-byte blob for the test
        certs629 = certs + bytes(mtpz.CERT_LENGTH - len(certs))
        acm = mtpz.build_acm(keys, certs629, bytes(range(16)))
        self.assertEqual(len(acm), 785)
        self.assertTrue(mtpz.verify_acm(acm, keys))


if __name__ == "__main__":
    unittest.main(verbosity=2)
