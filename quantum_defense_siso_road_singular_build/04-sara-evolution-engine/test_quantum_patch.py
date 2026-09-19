import unittest
from unittest.mock import patch

from fastapi import HTTPException
import quantum_patch as q

class Snapshot:
    def __init__(self, data=None): self._data=data
    @property
    def exists(self): return self._data is not None
    def to_dict(self): return self._data

class Ref:
    def __init__(self, existing=None): self.existing=existing; self._client=self
    def transaction(self): return object()
    def get(self, transaction=None): return Snapshot(self.existing)

class Transaction:
    def __init__(self): self.created=[]
    def create(self, ref, entry): self.created.append(entry)

class QuantumPatchTests(unittest.TestCase):
    def test_standard_names_and_aliases_are_current(self):
        self.assertEqual(q._decision_for("ML-KEM-1024")["standard"], "FIPS 203")
        self.assertEqual(q._decision_for("CRYSTALS-Dilithium-L5")["standard"], "FIPS 204")

    def test_unknown_algorithm_is_monitored(self):
        self.assertEqual(q._decision_for("Future-PQC")["decision"], "MONITOR")

    def test_hash_is_order_independent(self):
        self.assertEqual(q._hash({"a":1,"b":2}), q._hash({"b":2,"a":1}))

    def test_retry_ignores_timestamp_but_rejects_content_change(self):
        base = {"algorithm":"ML-KEM-1024","decision":"CURRENT","nist_status":"standardized","standard":"FIPS 203","reason":"same","database_version":q.DATABASE_VERSION,"patch":q.PATCH_VERSION,"timestamp_epoch":1}
        retry = {**base, "timestamp_epoch":2}
        changed = {**retry, "reason":"different"}
        self.assertTrue(q._same_recommendation(base, retry))
        self.assertFalse(q._same_recommendation(base, changed))

    def test_persistence_failure_is_not_silently_accepted(self):
        with patch.object(q, "_collection", side_effect=RuntimeError("firestore down")):
            with self.assertRaises(RuntimeError): q._persist_recommendation({"recommendation_id":"x","entry_hash_sha3_512":"h"})

if __name__ == "__main__": unittest.main()

