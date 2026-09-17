import hashlib

import pytest


def test_sentence_segmentation_is_deterministic_and_digest_bound():
    from sara_unified.voice.segmenting import split_sentences

    segments = split_sentences("SARA is online. Voice 1.1 is ready!", max_segments=8)

    assert [segment.segment_id for segment in segments] == ["seg-0001", "seg-0002"]
    assert [segment.text for segment in segments] == ["SARA is online.", "Voice 1.1 is ready!"]
    assert segments[0].text_sha256 == hashlib.sha256(b"SARA is online.").hexdigest()


def test_sentence_segmentation_rejects_empty_and_excessive_segments():
    from sara_unified.voice.segmenting import split_sentences

    with pytest.raises(ValueError, match="voice text must not be empty"):
        split_sentences("   ")
    with pytest.raises(ValueError, match="too many voice segments"):
        split_sentences("One. Two. Three.", max_segments=2)


def test_speech_rate_presets_are_bounded_and_no_arbitrary_float_is_accepted():
    from sara_unified.voice.controls import speech_controls_for

    assert speech_controls_for("slower").length_scale == 1.16
    assert speech_controls_for("normal").length_scale == 1.08
    assert speech_controls_for("faster").length_scale == 1.00
    with pytest.raises(ValueError, match="unsupported speech rate"):
        speech_controls_for("1.37")


def test_pronunciation_dictionary_applies_ordered_rules_and_exposes_digest():
    from sara_unified.voice.pronunciation import PronunciationDictionary, PronunciationRule

    dictionary = PronunciationDictionary(
        dictionary_id="sara-default",
        version="2026.09.17",
        rules=(
            PronunciationRule(match="SARA", replacement="Sarah"),
            PronunciationRule(match="OMEGA", replacement="Omega"),
        ),
    )

    result = dictionary.apply("SARA OMEGA is live.")

    assert result.text == "Sarah Omega is live."
    assert result.dictionary_id == "sara-default"
    assert result.dictionary_version == "2026.09.17"
    assert len(result.dictionary_sha256) == 64
    assert result.applied_rules == ["SARA", "OMEGA"]


def test_audio_receipt_binds_source_segment_audio_controls_and_dictionary():
    from sara_unified.voice.controls import speech_controls_for
    from sara_unified.voice.pronunciation import PronunciationDictionary
    from sara_unified.voice.receipts import build_audio_receipt

    dictionary = PronunciationDictionary.default()
    controls = speech_controls_for("normal")

    receipt = build_audio_receipt(
        job_id="voice-job-1",
        segment_id="seg-0001",
        source_response_sha256="a" * 64,
        segment_text="SARA is live.",
        transformed_segment_text="Sarah is live.",
        audio=b"RIFFaudio",
        speech_rate="normal",
        controls=controls,
        dictionary=dictionary,
        source_commit_sha="30c1f606092b6d4043413a185d8e0ac8d3458de2",
        deployment_id="unit-deployment",
        voice_service_url="http://sara-piper-voice.railway.internal:8080",
        duration_ms=25,
    )

    assert receipt.profile_id == "sara_elegant_british_v1"
    assert receipt.model_id == "en_GB-cori-high"
    assert receipt.audio_sha256 == hashlib.sha256(b"RIFFaudio").hexdigest()
    assert receipt.voice_service_url_hash != "http://sara-piper-voice.railway.internal:8080"
    assert "token" not in repr(receipt).lower()
