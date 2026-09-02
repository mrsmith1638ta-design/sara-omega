from __future__ import annotations

import re
from statistics import mean, median

from .base import Specialist
from ..models import Assignment, Claim, SpecialistResult


class DataAnalyticsSpecialist(Specialist):
    name = "data_analytics"

    async def run(self, assignment: Assignment) -> SpecialistResult:
        numbers = [float(value) for value in re.findall(r"[-+]?\d+(?:\.\d+)?", assignment.task)]
        if not numbers:
            return SpecialistResult(
                provider=self.name,
                role=assignment.role,
                task=assignment.task,
                success=False,
                error="No numeric dataset or metric values were supplied for data analytics.",
            )

        stats = {
            "count": len(numbers),
            "min": min(numbers),
            "max": max(numbers),
            "mean": mean(numbers),
            "median": median(numbers),
        }
        answer = (
            "Data analytics specialist computed descriptive statistics: "
            f"count={stats['count']}, min={stats['min']}, max={stats['max']}, "
            f"mean={stats['mean']:.4f}, median={stats['median']:.4f}."
        )
        return SpecialistResult(
            provider=self.name,
            role=assignment.role,
            task=assignment.task,
            answer=answer,
            claims=[Claim(provider=self.name, statement=answer, confidence=0.7)],
            raw={"statistics": stats},
        )
