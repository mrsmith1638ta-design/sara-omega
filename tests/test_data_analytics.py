import asyncio

from app.models import Assignment
from app.providers.data_analytics import DataAnalyticsSpecialist


def test_data_analytics_specialist_computes_descriptive_stats():
    result = asyncio.run(DataAnalyticsSpecialist().run(
        Assignment(
            provider="data_analytics",
            role="data analytics",
            task="Analyze metric values 10, 20, and 30.",
        )
    ))

    assert result.success is True
    assert result.raw["statistics"]["count"] == 3
    assert result.raw["statistics"]["mean"] == 20


def test_data_analytics_specialist_requires_actual_numbers():
    result = asyncio.run(DataAnalyticsSpecialist().run(
        Assignment(
            provider="data_analytics",
            role="data analytics",
            task="Analyze the dashboard metrics.",
        )
    ))

    assert result.success is False
    assert "No numeric dataset" in result.error
