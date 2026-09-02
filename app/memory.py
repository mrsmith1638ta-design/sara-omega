from __future__ import annotations
from contextlib import closing
import json, os, sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path
from .models import Problem, Verdict

class DecisionLedger:
    def __init__(self):
        data_dir = Path(os.getenv("SARA_DATA_DIR", "./data"))
        data_dir.mkdir(parents=True, exist_ok=True)
        self.db = data_dir / "sara_omega.db"
        with closing(sqlite3.connect(self.db)) as c:
            with c:
                c.execute('''CREATE TABLE IF NOT EXISTS decisions(
                    id TEXT PRIMARY KEY, created_at TEXT NOT NULL, query TEXT NOT NULL,
                    problem_json TEXT NOT NULL, verdict_json TEXT NOT NULL,
                    outcome_json TEXT, lesson TEXT)''')

    def record(self, p: Problem, v: Verdict) -> str:
        did = str(uuid.uuid4())
        with closing(sqlite3.connect(self.db)) as c:
            with c:
                c.execute("INSERT INTO decisions VALUES(?,?,?,?,?,?,?)", (
                    did, datetime.now(timezone.utc).isoformat(), p.query,
                    p.model_dump_json(), v.model_dump_json(), None, None))
        return did

    def record_outcome(self, decision_id: str, outcome: dict, lesson: str | None = None):
        with closing(sqlite3.connect(self.db)) as c:
            with c:
                c.execute("UPDATE decisions SET outcome_json=?, lesson=? WHERE id=?",
                          (json.dumps(outcome), lesson, decision_id))

    def recent(self, limit: int = 10) -> list[dict]:
        with closing(sqlite3.connect(self.db)) as c:
            rows = c.execute("SELECT id,created_at,query,verdict_json,outcome_json,lesson FROM decisions ORDER BY created_at DESC LIMIT ?",
                             (limit,)).fetchall()
        return [{"id":r[0],"created_at":r[1],"query":r[2],"verdict":json.loads(r[3]),
                 "outcome":json.loads(r[4]) if r[4] else None,"lesson":r[5]} for r in rows]
