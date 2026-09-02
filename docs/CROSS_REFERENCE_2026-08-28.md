# Architecture cross-reference — 2026-08-28

This implementation was checked against current official documentation before packaging.

## OpenAI / Codex
- OpenAI's current developer documentation lists GPT-5.6 as the flagship model family.
- OpenAI documents the Responses API for programmatic model responses.
- OpenAI documents Codex as an embeddable/automatable coding agent and previously announced
  the Codex SDK plus `codex exec` for shell workflows.
- This repository uses the Responses API for the SARA semantic judge and `codex exec`
  as the conservative local Codex integration boundary.

## Cursor
- Cursor's current documentation says the CLI command is `agent`.
- Non-interactive operation uses `-p/--print`, and structured/text output formats are supported.
- Cursor documents `agent acp` for custom JSON-RPC clients and MCP for external tools/data.
- Cursor reads `AGENTS.md` and `.cursor/rules`.
- This repository uses non-interactive Ask mode for a read-oriented specialist boundary and
  ships both AGENTS.md and a Cursor rule. ACP is the recommended future deeper adapter.

## Perplexity
- Current Sonar documentation exposes `POST https://api.perplexity.ai/v1/sonar`.
- Current documented model options include sonar, sonar-pro, sonar-deep-research and sonar-reasoning-pro.
- Responses can include citations and search_results.
- This repository uses `/v1/sonar`, defaults to `sonar-pro`, and preserves search results as Evidence.

## Accuracy boundary
Documentation compatibility does not prove provider availability, subscription entitlement,
API credentials, local CLI installation, or semantic correctness. Live integration tests require
the user's own configured environments and credentials.
