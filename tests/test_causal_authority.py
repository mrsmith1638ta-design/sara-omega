from app.unified_fusion import (
    CausalAuthorityEngine,
    CausalEffect,
    CausalFinalityDecision,
    CausalNode,
    CausalScopeApproval,
)


def test_causal_finality_allows_only_approved_downstream_effects():
    engine = CausalAuthorityEngine()
    approval = CausalScopeApproval(
        approval_id="approval-1",
        transaction_id="tx-1",
        approved_effects={
            CausalEffect(resource="profile:123", effect="update", boundary="display_name"),
            CausalEffect(resource="audit:123", effect="append", boundary="profile_change"),
        },
    )

    decision = engine.reconcile_finality(
        approval,
        actual_effects={
            CausalEffect(resource="audit:123", effect="append", boundary="profile_change"),
            CausalEffect(resource="profile:123", effect="update", boundary="display_name"),
        },
    )

    assert decision.decision == CausalFinalityDecision.ACCEPT
    assert decision.unapproved_effects == set()
    assert decision.missing_effects == set()
    assert decision.quarantined is False


def test_causal_finality_quarantines_effects_outside_approved_envelope():
    engine = CausalAuthorityEngine()
    approval = CausalScopeApproval(
        approval_id="approval-2",
        transaction_id="tx-2",
        approved_effects={CausalEffect(resource="profile:123", effect="update", boundary="display_name")},
    )

    decision = engine.reconcile_finality(
        approval,
        actual_effects={
            CausalEffect(resource="profile:123", effect="update", boundary="display_name"),
            CausalEffect(resource="billing:123", effect="charge", boundary="subscription"),
        },
    )

    assert decision.decision == CausalFinalityDecision.QUARANTINE
    assert CausalEffect(resource="billing:123", effect="charge", boundary="subscription") in decision.unapproved_effects
    assert "CAUSAL_SCOPE_VIOLATION" in decision.blockers
    assert decision.quarantined is True


def test_causal_finality_compares_effects_not_command_identity():
    engine = CausalAuthorityEngine()
    approval = CausalScopeApproval(
        approval_id="approval-3",
        transaction_id="tx-3",
        command_identity="same-command",
        approved_effects={CausalEffect(resource="artifact:alpha", effect="write", boundary="draft")},
    )

    decision = engine.reconcile_finality(
        approval,
        actual_effects={CausalEffect(resource="artifact:alpha", effect="publish", boundary="public")},
        actual_command_identity="same-command",
    )

    assert decision.decision == CausalFinalityDecision.QUARANTINE
    assert "COMMAND_MATCH_DOES_NOT_OVERRIDE_CAUSAL_MISMATCH" in decision.blockers


def test_transitive_authority_revocation_suspends_descendants_of_compromised_node():
    engine = CausalAuthorityEngine()
    graph = [
        CausalNode(node_id="source-a", depends_on=set(), execution_authority=True),
        CausalNode(node_id="memory-b", depends_on={"source-a"}, execution_authority=True),
        CausalNode(node_id="artifact-c", depends_on={"memory-b"}, execution_authority=True),
        CausalNode(node_id="independent-d", depends_on=set(), execution_authority=True),
    ]

    result = engine.revoke_transitive_authority(graph, compromised_node_ids={"source-a"})

    assert result.revoked_node_ids == {"source-a", "memory-b", "artifact-c"}
    assert result.suspended_execution_authority == {"source-a", "memory-b", "artifact-c"}
    assert "independent-d" not in result.revoked_node_ids
    assert result.updated_nodes["artifact-c"].execution_authority is False
    assert result.updated_nodes["independent-d"].execution_authority is True
