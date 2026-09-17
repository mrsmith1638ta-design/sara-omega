import pytest

from app.unified_fusion import (
    Decision,
    EvidenceState,
    FusionRequest,
    ModuleResult,
    ModuleStatus,
    SaraFusionEngine,
    SaraModule,
)


@pytest.mark.asyncio
async def test_analysis_allows_without_execution_authority():
    response = await SaraFusionEngine().execute(
        FusionRequest(
            tenant_id="tenant-1",
            actor_id="actor-1",
            objective="evaluate fusion architecture",
            payload={"feature": "SARA_CORE"},
            actor_scopes={"sara.solve"},
        )
    )

    assert response.decision == Decision.ALLOW
    assert response.production_authority is False
    assert response.release_authority is False
    assert response.blockers == []
    assert response.module_results["enterprise_governance"].status == ModuleStatus.OK


@pytest.mark.asyncio
async def test_missing_actor_or_tenant_denies_before_modules_run():
    response = await SaraFusionEngine().execute(
        FusionRequest(
            tenant_id="",
            actor_id="actor-1",
            objective="evaluate",
        )
    )

    assert response.decision == Decision.DENY
    assert response.blockers == ["MISSING_TENANT"]
    assert response.module_results == {}


@pytest.mark.asyncio
async def test_release_requires_road_and_fails_closed_without_authoritative_road():
    response = await SaraFusionEngine().execute(
        FusionRequest(
            tenant_id="tenant-1",
            actor_id="actor-1",
            objective="release candidate",
            requested_action="RELEASE",
            candidate_commit="4524e2dcb1aa063865a253a902ae7adc3bd067c7",
            actor_scopes={"sara.solve", "sara.execute"},
        )
    )

    assert response.decision == Decision.DENY
    assert "ROAD_AUTHORITY_REQUIRED" in response.blockers
    assert f"ROAD:{EvidenceState.UNVERIFIED.value}" in response.blockers
    assert "Submit exact candidate evidence to authoritative ROAD." in response.required_actions
    assert response.release_authority is False


class IllegalAuthorityModule(SaraModule):
    name = "illegal_authority"

    async def evaluate(self, request, context):
        return ModuleResult(
            module=self.name,
            status=ModuleStatus.OK,
            execution_authority=True,
            release_authority=True,
        )


@pytest.mark.asyncio
async def test_child_module_cannot_self_grant_execution_or_release_authority():
    engine = SaraFusionEngine(modules=[IllegalAuthorityModule()])

    response = await engine.execute(
        FusionRequest(
            tenant_id="tenant-1",
            actor_id="actor-1",
            objective="try to self-authorize",
            payload={"feature": "SARA_CORE"},
            actor_scopes={"sara.solve"},
        )
    )

    assert response.decision == Decision.DENY
    assert "illegal_authority:ILLEGAL_SELF_EXECUTION_AUTHORITY" in response.blockers
    assert "illegal_authority:ILLEGAL_SELF_RELEASE_AUTHORITY" in response.blockers
    assert response.production_authority is False
    assert response.release_authority is False


class FailingModule(SaraModule):
    name = "failing_module"

    async def evaluate(self, request, context):
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_module_exception_becomes_failed_result_and_blocker():
    response = await SaraFusionEngine(modules=[FailingModule()]).execute(
        FusionRequest(
            tenant_id="tenant-1",
            actor_id="actor-1",
            objective="evaluate",
            actor_scopes={"sara.solve"},
        )
    )

    assert response.decision == Decision.DENY
    assert response.module_results["failing_module"].status == ModuleStatus.FAILED
    assert "failing_module:FAILED" in response.blockers
    assert "failing_module:MODULE_FAILURE" in response.blockers


@pytest.mark.asyncio
async def test_evidence_hash_is_deterministic_for_same_request():
    request = FusionRequest(
        tenant_id="tenant-1",
        actor_id="actor-1",
        objective="stable hash",
        payload={"feature": "SARA_CORE"},
        actor_scopes={"sara.solve"},
    )

    first = await SaraFusionEngine().execute(request)
    second = await SaraFusionEngine().execute(request)

    assert first.evidence_hash
    assert first.evidence_hash == second.evidence_hash
