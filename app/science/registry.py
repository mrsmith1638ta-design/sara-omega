from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import ProvenanceClass


class RegistryError(ValueError):
    pass


class ScienceRegistry:
    def __init__(self, equations_path: str | Path, sources_path: str | Path):
        self.equations_path = Path(equations_path)
        self.sources_path = Path(sources_path)
        self.sources = self._load_records(self.sources_path, "source")
        self.equations = self._load_records(self.equations_path, "equation")
        self._validate()

    @staticmethod
    def _load_records(path: Path, kind: str) -> dict[str, dict[str, Any]]:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RegistryError(f"{kind}_registry_unreadable") from exc
        if not isinstance(raw, list):
            raise RegistryError(f"{kind}_registry_must_be_list")
        records: dict[str, dict[str, Any]] = {}
        for record in raw:
            if not isinstance(record, dict) or not record.get("id"):
                raise RegistryError(f"{kind}_missing_id")
            identifier = str(record["id"])
            if identifier in records:
                raise RegistryError(f"duplicate_{kind}_id:{identifier}")
            records[identifier] = record
        return records

    def _validate(self) -> None:
        allowed = {item.value for item in ProvenanceClass}
        for source_id, source in self.sources.items():
            if source.get("provenance_class") not in allowed:
                raise RegistryError(f"invalid_source_provenance:{source_id}")
            if not source.get("title") or not source.get("evidence_status"):
                raise RegistryError(f"incomplete_source:{source_id}")
        for equation_id, equation in self.equations.items():
            if equation.get("provenance_class") not in allowed:
                raise RegistryError(f"invalid_equation_provenance:{equation_id}")
            for source_id in equation.get("source_ids", []):
                if source_id not in self.sources:
                    raise RegistryError(f"missing_source_reference:{equation_id}:{source_id}")
            if "symbolic_form" not in equation or "variables" not in equation or "units" not in equation:
                raise RegistryError(f"incomplete_equation:{equation_id}")

    @classmethod
    def default(cls) -> "ScienceRegistry":
        root = Path(__file__).resolve().parents[2]
        return cls(root / "data/science/equations/core.json", root / "data/science/sources/core.json")

    def get_equation(self, equation_id: str) -> dict[str, Any]:
        try:
            return self.equations[equation_id]
        except KeyError as exc:
            raise RegistryError(f"unknown_equation:{equation_id}") from exc

    def get_source(self, source_id: str) -> dict[str, Any]:
        try:
            return self.sources[source_id]
        except KeyError as exc:
            raise RegistryError(f"unknown_source:{source_id}") from exc
