import unittest
from unittest.mock import patch
import raft_pqc_patch as r

class FakeResponse:
    def __init__(self,payload): self.payload=payload
    def __enter__(self): return self
    def __exit__(self,*_): return False
    def read(self): return __import__("json").dumps(self.payload).encode()

class RaftPatchTests(unittest.TestCase):
    def test_canonical_vote_is_order_independent(self):
        self.assertEqual(r._vote_hash({"term":1,"candidate_id":"n1"}), r._vote_hash({"candidate_id":"n1","term":1}))
    def test_default_is_migration_mode(self):
        with patch.dict("os.environ", {}, clear=True): self.assertFalse(r._strict())
    def test_native_ml_dsa_required(self):
        result={"algorithm":"ML-DSA-87","mode":"liboqs_native","valid":True}
        with patch.object(r,"_identity_token",return_value="t"), patch("urllib.request.urlopen",return_value=FakeResponse(result)), patch.dict("os.environ",{"SARA_PQC_PPSIM_URL":"https://ppsim"}):
            self.assertTrue(r._verify_signature("{}","sig")["valid"])
    def test_fallback_mode_rejected(self):
        result={"algorithm":"ML-DSA-87","mode":"fallback","valid":True}
        with patch.object(r,"_identity_token",return_value="t"), patch("urllib.request.urlopen",return_value=FakeResponse(result)), patch.dict("os.environ",{"SARA_PQC_PPSIM_URL":"https://ppsim"}):
            with self.assertRaisesRegex(RuntimeError,"not native"): r._verify_signature("{}","sig")


class FakeSnapshot:
    def __init__(self, exists=False, data=None):
        self.exists = exists
        self._data = data or {}
    def to_dict(self): return self._data

class FakeProposalRef:
    def __init__(self, snapshot): self.snapshot = snapshot
    def get(self, transaction=None): return self.snapshot

class FakeTransaction:
    def __init__(self): self.update = None
    def set(self, ref, update, merge=False): self.update = update

class DurableQuorumTests(unittest.TestCase):
    def test_proposal_id_required(self):
        with self.assertRaisesRegex(ValueError, "proposal_id_required"):
            r._proposal_id({"term": 1})

    def test_first_unique_node_does_not_commit(self):
        tx = FakeTransaction(); ref = FakeProposalRef(FakeSnapshot())
        entry = {"proposal_id":"p1","node_id":"n1","vote_hash_sha3_512":"h"}
        result = r._record_verified_vote_impl(tx, ref, entry)
        self.assertFalse(result["committed"])
        self.assertEqual(1, result["quorum_count"])

    def test_second_unique_node_commits(self):
        prior = {"vote_hash_sha3_512":"h","votes":{"n1":{"node_id":"n1"}},"committed":False}
        tx = FakeTransaction(); ref = FakeProposalRef(FakeSnapshot(True, prior))
        entry = {"proposal_id":"p1","node_id":"n2","vote_hash_sha3_512":"h"}
        result = r._record_verified_vote_impl(tx, ref, entry)
        self.assertTrue(result["committed"])
        self.assertEqual(["n1", "n2"], result["attested_nodes"])

    def test_duplicate_node_cannot_increase_quorum(self):
        prior = {"vote_hash_sha3_512":"h","votes":{"n1":{"node_id":"n1"}},"committed":False}
        tx = FakeTransaction(); ref = FakeProposalRef(FakeSnapshot(True, prior))
        entry = {"proposal_id":"p1","node_id":"n1","vote_hash_sha3_512":"h"}
        result = r._record_verified_vote_impl(tx, ref, entry)
        self.assertTrue(result["duplicate"])
        self.assertEqual(1, result["quorum_count"])

if __name__=="__main__": unittest.main()
