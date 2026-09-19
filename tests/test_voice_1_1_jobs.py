class FakeVoiceClient:
    def __init__(self, stop_after_first=False):
        self.calls = []
        self.stop_after_first = stop_after_first
        self.manager = None
        self.job_id = None

    def synthesize_with_controls(self, text, controls):
        self.calls.append((text, controls.length_scale))
        if self.stop_after_first and len(self.calls) == 1:
            self.manager.stop_job(self.job_id)
        return b"RIFFfake-segment"


def test_voice_job_creates_segment_receipts_without_raw_text_by_default():
    from sara_unified.voice.jobs import VoiceJobManager

    fake = FakeVoiceClient()
    manager = VoiceJobManager(
        voice_client=fake,
        source_commit_sha="unit-sha",
        deployment_id="unit-deployment",
        voice_service_url="http://voice.internal:8080",
    )

    job = manager.create_job(
        text="SARA is online. Voice 1.1 is ready.",
        speech_rate="normal",
        preserve_transcript=False,
        return_audio="segments",
    )

    assert job.status == "completed"
    assert len(job.segments) == 2
    assert len(job.receipts) == 2
    assert len(job.audio_segments) == 2
    assert "SARA is online" not in repr(job.public_dict(include_transcript=False))
    assert fake.calls[0][0] == "Sarah is online."


def test_voice_job_preserves_transcript_only_when_requested():
    from sara_unified.voice.jobs import VoiceJobManager

    manager = VoiceJobManager(
        voice_client=FakeVoiceClient(),
        source_commit_sha="unit-sha",
        deployment_id="unit-deployment",
        voice_service_url="http://voice.internal:8080",
    )

    hidden = manager.create_job(text="Private sentence.", preserve_transcript=False)
    preserved = manager.create_job(text="Preserved sentence.", preserve_transcript=True)

    assert hidden.transcript is None
    assert preserved.transcript == "Preserved sentence."


def test_voice_job_stop_is_idempotent_and_prevents_later_segments():
    from sara_unified.voice.jobs import VoiceJobManager

    fake = FakeVoiceClient(stop_after_first=True)
    manager = VoiceJobManager(
        voice_client=fake,
        source_commit_sha="unit-sha",
        deployment_id="unit-deployment",
        voice_service_url="http://voice.internal:8080",
    )
    fake.manager = manager

    job = manager.start_job(
        text="First sentence. Second sentence. Third sentence.",
        speech_rate="normal",
        preserve_transcript=False,
        return_audio="none",
    )
    fake.job_id = job.job_id
    completed = manager.run_job(job.job_id)
    stopped_again = manager.stop_job(job.job_id)

    assert completed.status == "stopped"
    assert stopped_again.status == "stopped"
    assert len(fake.calls) == 1
    assert completed.stop_requested_at is not None


def test_voice_job_rejects_unsupported_audio_return_mode():
    import pytest
    from sara_unified.voice.jobs import VoiceJobManager

    manager = VoiceJobManager(
        voice_client=FakeVoiceClient(),
        source_commit_sha="unit-sha",
        deployment_id="unit-deployment",
        voice_service_url="http://voice.internal:8080",
    )

    with pytest.raises(ValueError, match="unsupported return_audio"):
        manager.create_job(text="Hello.", return_audio="wav_archive")
