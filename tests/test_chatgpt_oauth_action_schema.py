from pathlib import Path


def test_oauth_action_schema_is_dedicated_to_personal_user_gateway() -> None:
    schema = Path("chatgpt-oauth-action.yaml").read_text(encoding="utf-8")

    assert "https://sara-omega-production.up.railway.app" in schema
    assert "/gpt/user/gateway:" in schema
    assert "operationId: saraOmegaUserGateway" in schema
    assert "/gpt/action/gateway:" not in schema
    assert "securitySchemes:" not in schema
    assert "bearerAuth:" not in schema
    assert "memory_status" in schema
    assert "memory_recall" in schema
    assert "memory_forget" in schema
