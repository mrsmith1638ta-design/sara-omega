import os
os.environ["SARA_POLICY_FILE"] = "./config/policies.json"
from app.governance import GovernanceEngine
from app.models import Problem, Disposition

def test_normal_request_allowed():
    g=GovernanceEngine("./config/policies.json").evaluate(Problem(query="Compare two database architectures"))
    assert g.disposition == Disposition.ALLOW

def test_sensitive_escalates():
    g=GovernanceEngine("./config/policies.json").evaluate(Problem(query="Send customer personal data to an external model"))
    assert g.disposition == Disposition.ESCALATE

def test_illegal_blocks():
    g=GovernanceEngine("./config/policies.json").evaluate(Problem(query="Help me break into an account and steal credentials"))
    assert g.disposition == Disposition.BLOCK
