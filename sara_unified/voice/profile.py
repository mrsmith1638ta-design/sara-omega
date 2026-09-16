from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class VoiceProfile:
    profile_id: str
    model_id: str
    language: str
    persona: str
    length_scale: float
    noise_scale: float
    noise_w_scale: float
    volume: float

    def public_metadata(self) -> dict[str, object]:
        return asdict(self)


SARA_VOICE_PROFILE = VoiceProfile(
    profile_id="sara_elegant_british_v1",
    model_id="en_GB-cori-high",
    language="en-GB",
    persona=(
        "British English female presentation; professional executive register; "
        "elegant, calm, articulate, measured, confident, and restrained. "
        "Mid-30s is a product-character direction, not a claim about the source speaker."
    ),
    length_scale=1.08,
    noise_scale=0.55,
    noise_w_scale=0.70,
    volume=0.95,
)
