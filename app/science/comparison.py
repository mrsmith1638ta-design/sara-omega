from __future__ import annotations

from .models import EngineeringState


def compare_levitation_systems() -> dict[str, dict[str, object]]:
    return {
        "EMS": {
            "mechanism": "electromagnetic attraction",
            "active_control": EngineeringState.REQUIRED.value,
            "passive_restoring_behavior": EngineeringState.NOT_REQUIRED.value,
            "low_speed_levitation": EngineeringState.REQUIRED.value,
            "high_speed_suitability": "DOCUMENTED_SYSTEM_CAPABILITY",
            "thermal_constraint": "coil and power-electronics heating",
            "maturity": "DOCUMENTED_TECHNOLOGY",
            "guideway": "ferromagnetic rail/stator and tightly controlled air gap",
            "applicability_scope": "CONVENTIONAL_EMS",
            "dependencies": ["air-gap controller", "guideway geometry", "power electronics"],
        },
        "EDS": {
            "mechanism": "electrodynamic interaction with induced currents / superconducting magnets where applicable",
            "active_control": EngineeringState.SYSTEM_DEPENDENT.value,
            "passive_restoring_behavior": EngineeringState.SYSTEM_DEPENDENT.value,
            "low_speed_levitation": EngineeringState.SYSTEM_DEPENDENT.value,
            "high_speed_suitability": "SYSTEM_DEPENDENT",
            "thermal_constraint": "cryogenic system when superconducting magnets are used",
            "maturity": "DOCUMENTED_TECHNOLOGY_OR_ENGINEERING_MODEL",
            "guideway": "conductive or coil guideway with system-specific transition speed",
            "dependencies": [
                "guideway topology",
                "onboard magnet architecture",
                "damping method",
                "transition speed",
                "conductor/coil arrangement",
                "control strategy",
            ],
        },
        "HTS": {
            "mechanism": "flux pinning / superconducting magnetic interaction",
            "active_control": EngineeringState.SYSTEM_DEPENDENT.value,
            "passive_restoring_behavior": EngineeringState.SYSTEM_DEPENDENT.value,
            "low_speed_levitation": EngineeringState.SYSTEM_DEPENDENT.value,
            "high_speed_suitability": "SYSTEM_DEPENDENT",
            "thermal_constraint": "cryogenic temperature below material critical temperature",
            "maturity": "EXPERIMENTAL_TECHNOLOGY",
            "guideway": "permanent-magnet or field-source guideway depending on configuration",
            "dependencies": [
                "material",
                "temperature",
                "field history",
                "guideway configuration",
                "geometry",
                "critical current density",
            ],
        },
    }
