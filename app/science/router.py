from __future__ import annotations


class ScienceRouter:
    def route_text(self, text: str) -> list[str]:
        q = text.lower()
        selected: list[str] = []
        if any(token in q for token in ("egypt", "giza", "pyramid", "seked", "rhind", "moscow papyrus")):
            selected.append("ancient_egypt")
        if any(token in q for token in ("greek", "roman", "vitruvi", "ionic", "doric", "corinthian", "column", "arch", "vault", "dome", "aqueduct", "amphitheater")):
            selected.append("classical_greek_roman")
        if any(token in q for token in ("engineering", "drag", "aerodynamic", "statics", "structural", "load", "stress", "speed", "maglev")):
            selected.append("engineering")
        if any(token in q for token in ("ems", "electromagnetic suspension", "china maglev", "maglev")):
            selected.append("maglev_ems")
        if any(token in q for token in ("eds", "electrodynamic suspension", "superconducting maglev", "superconducting")):
            selected.append("maglev_eds")
        if any(token in q for token in ("hts", "high-temperature superconductor", "flux pinning")):
            selected.append("maglev_hts")
        return list(dict.fromkeys(selected))
