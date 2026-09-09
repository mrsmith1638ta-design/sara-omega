from pathlib import Path


CONFIG = Path(__file__).resolve().parents[1] / "GPT_V321_CONFIG.md"


def test_gpt_v321_config_includes_current_ats_system_guidance():
    text = CONFIG.read_text(encoding="utf-8")

    assert "### 2026 ATS and AI hiring-system mode" in text
    assert "Workday" in text
    assert "Greenhouse" in text
    assert "Lever" in text
    assert "iCIMS" in text
    assert "SmartRecruiters" in text
    assert "SAP SuccessFactors" in text
    assert "Ashby" in text
    assert "Taleo/Oracle" in text
    assert "NYC Local Law 144" in text
    assert "EEOC adverse-impact" in text
    assert "Never recommend hidden text, prompt injection, fake experience" in text
