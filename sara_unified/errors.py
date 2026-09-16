class SARAError(Exception):
    code = "SARA_ERROR"

class AuthenticationError(SARAError): code = "AUTHENTICATION_FAILED"
class AuthorizationError(SARAError): code = "AUTHORIZATION_DENIED"
class ReplayError(SARAError): code = "REPLAY_OR_FRESHNESS_FAILED"
class GovernanceUnavailableError(SARAError): code = "GOVERNANCE_UNAVAILABLE"
class PolicyDeniedError(SARAError): code = "POLICY_DENIED"
class IntegrityError(SARAError): code = "INTEGRITY_VIOLATION"
class RecoveryDeniedError(SARAError): code = "RECOVERY_DENIED"
class EvidenceInsufficientError(SARAError): code = "EVIDENCE_INSUFFICIENT"
