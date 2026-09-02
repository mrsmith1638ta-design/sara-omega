from __future__ import annotations

import tools.custom_gpt_action_sync_resolver as resolver


VALID_SCHEMA = """
openapi: 3.1.0
info:
  title: SARA-OMEGA V3.2.1 Runtime and Governed Action Gateway
  version: 3.2.1
servers:
  - url: https://sara-omega-production.up.railway.app
paths:
  /:
    get:
      operationId: getSaraOmegaIdentity
  /health/ready:
    get:
      operationId: getSaraOmegaReadiness
  /health/production-acceptance:
    get:
      operationId: getSaraOmegaProductionAcceptance
  /context-dev/status:
    get:
      operationId: getContextDevAuthorizationStatus
  /gpt/action/gateway:
    post:
      operationId: saraOmegaGovernedGateway
      security:
        - bearerAuth: []
components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
  schemas:
    SaraOmegaGatewayRequest:
      properties:
        operation:
          enum:
            - status
            - production_acceptance
            - module_awareness
            - runtime_assurance
            - concentration
            - hawkins_chaos
            - titan_health
            - solve
            - verify_output
"""


def test_validate_schema_contract_accepts_complete_action_schema():
    result = resolver.validate_schema_contract(VALID_SCHEMA)

    assert result["pass"] is True
    assert "saraOmegaGovernedGateway" in result["operation_ids"]
    assert "verify_output" in result["gateway_operations"]
    assert result["missing_operation_ids"] == []
    assert result["missing_gateway_operations"] == []


def test_validate_schema_contract_fails_closed_when_gateway_operation_missing():
    incomplete = VALID_SCHEMA.replace("            - verify_output\n", "")

    result = resolver.validate_schema_contract(incomplete)

    assert result["pass"] is False
    assert "missing_gateway_operations" in result["failures"]
    assert result["missing_gateway_operations"] == ["verify_output"]


def test_normalize_schema_makes_line_endings_stable():
    assert resolver.normalize_schema("a: 1\r\nb: 2  \n") == "a: 1\nb: 2"
