from __future__ import annotations
import asyncio, json, os, shlex
from .base import Specialist
from ..models import Assignment, SpecialistResult, Claim

class LocalAgentSpecialist(Specialist):
    def __init__(self, name: str, command_env: str, default_command: str, args: list[str]):
        self.name = name
        self.command = os.getenv(command_env, default_command)
        self.args = args

    async def run(self, assignment: Assignment) -> SpecialistResult:
        if os.getenv("SARA_ALLOW_LOCAL_AGENTS", "false").lower() != "true":
            return SpecialistResult(provider=self.name, role=assignment.role, task=assignment.task,
                success=False, error="Local agent execution disabled. Set SARA_ALLOW_LOCAL_AGENTS=true after reviewing permissions.")
        cmd = [self.command, *self.args, assignment.task]
        try:
            proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE,
                                                        stderr=asyncio.subprocess.PIPE)
            out, err = await asyncio.wait_for(proc.communicate(), timeout=300)
            if proc.returncode != 0:
                return SpecialistResult(provider=self.name, role=assignment.role, task=assignment.task,
                                        success=False, error=err.decode(errors="replace")[:4000])
            text = out.decode(errors="replace")
            # Cursor JSON mode may return structured output; preserve raw text if parsing differs by version.
            return SpecialistResult(provider=self.name, role=assignment.role, task=assignment.task,
                answer=text, claims=[Claim(provider=self.name, statement=text, confidence=0.55)])
        except Exception as e:
            return SpecialistResult(provider=self.name, role=assignment.role, task=assignment.task,
                                    success=False, error=str(e))

class CodexSpecialist(LocalAgentSpecialist):
    def __init__(self):
        super().__init__("codex", "SARA_CODEX_COMMAND", "codex", ["exec"])

class CursorSpecialist(LocalAgentSpecialist):
    def __init__(self):
        super().__init__("cursor", "SARA_CURSOR_COMMAND", "agent", ["-p", "--output-format", "text", "--mode", "ask"])
