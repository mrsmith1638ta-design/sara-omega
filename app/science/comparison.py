from __future__ import annotations


def compare_levitation_systems() -> dict[str, dict[str, object]]:
    return {
        "EMS": {
            "mechanism": "electromagnetic attraction",
            "active_control": True,
            "passive_restoring_behavior": False,
            "low_speed_levitation": True,
            "high_speed_suitability": True,
            "thermal_constraint": "coil and power-electronics heating",
            "maturity": "DOCUMENTED_TECHNOLOGY",
            "guideway": "ferromagnetic rail/stator and tightly controlled air gap",
        },
        "EDS": {
            "mechanism": "electrodynamic interaction with induced currents / superconducting magnets where applicable",
            "active_control": False,
            "passive_restoring_behavior": True,
            "low_speed_levitation": False,
            "high_speed_suitability": True,
            "thermal_constraint": "cryogenic system when superconducting magnets are used",
            "maturity": "DOCUMENTED_TECHNOLOGY_OR_ENGINEERING_MODEL",
            "guideway": "conductive or coil guideway with system-specific transition speed",
        },
        "HTS": {
            "mechanism": "flux pinning / superconducting magnetic interaction",
            "active_control": False,
            "passive_restoring_behavior": True,
            "low_speed_levitation": True,
            "high_speed_suitability": "system-dependent",
            "thermal_constraint": "cryogenic temperature below material critical temperature",
            "maturity": "EXPERIMENTAL_TECHNOLOGY",
            "guideway": "permanent-magnet or field-source guideway depending on configuration",
        },
    }
