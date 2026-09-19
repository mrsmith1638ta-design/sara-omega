import unittest
from unittest.mock import patch

import integrity_patch

class FakeResponse:
    def __init__(self, payload): self.payload = payload
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def read(self):
        import json
        return json.dumps(self.payload).encode("utf-8")

class IntegrityPatchTests(unittest.TestCase):
    def test_canonical_hash_is_order_independent(self):
        self.assertEqual(integrity_patch._sha3({"a": 1, "b": 2}), integrity_patch._sha3({"b": 2, "a": 1}))

    def test_ppsim_accepts_native_ml_dsa(self):
        payload = {"algorithm": "ML-DSA-87", "mode": "liboqs_native", "valid": True}
        with patch.object(integrity_patch, "_identity_token", return_value="token"), patch("urllib.request.urlopen", return_value=FakeResponse(payload)), patch.dict("os.environ", {"SARA_PQC_PPSIM_URL": "https://ppsim.example"}):
            self.assertTrue(integrity_patch._call_ppsim("/v1/pqc/verify", {"message": "hash", "signature": "sig"})["valid"])

    def test_ppsim_rejects_non_native_mode(self):
        payload = {"algorithm": "ML-DSA-87", "mode": "fallback", "valid": True}
        with patch.object(integrity_patch, "_identity_token", return_value="token"), patch("urllib.request.urlopen", return_value=FakeResponse(payload)), patch.dict("os.environ", {"SARA_PQC_PPSIM_URL": "https://ppsim.example"}):
            with self.assertRaisesRegex(RuntimeError, "not native"):
                integrity_patch._call_ppsim("/v1/pqc/verify", {"message": "hash", "signature": "sig"})

if __name__ == "__main__": unittest.main()
