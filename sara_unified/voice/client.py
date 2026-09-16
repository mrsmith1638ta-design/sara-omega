import httpx

from .profile import SARA_VOICE_PROFILE


class VoiceSynthesisError(RuntimeError):
    pass


class PiperVoiceClient:
    def __init__(self, service_url: str, service_token: str, *, timeout_seconds: float = 15.0):
        url = service_url.strip().rstrip("/")
        token = service_token.strip()
        if not url:
            raise ValueError("Piper service URL is required")
        if not token:
            raise ValueError("Piper service token is required")
        if timeout_seconds <= 0:
            raise ValueError("Piper timeout must be positive")
        self.service_url = url
        self.service_token = token
        self.timeout_seconds = float(timeout_seconds)

    def synthesize(self, text: str) -> bytes:
        payload = {
            "text": text,
            "length_scale": SARA_VOICE_PROFILE.length_scale,
            "noise_scale": SARA_VOICE_PROFILE.noise_scale,
            "noise_w_scale": SARA_VOICE_PROFILE.noise_w_scale,
            "volume": SARA_VOICE_PROFILE.volume,
        }
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    f"{self.service_url}/synthesize",
                    headers={"X-SARA-VOICE-TOKEN": self.service_token},
                    json=payload,
                )
        except httpx.HTTPError as exc:
            raise VoiceSynthesisError("Piper service unavailable") from exc

        if response.status_code != 200:
            raise VoiceSynthesisError(f"Piper service returned HTTP {response.status_code}")
        if not response.headers.get("content-type", "").lower().startswith("audio/wav"):
            raise VoiceSynthesisError("Piper service returned a non-WAV response")
        if not response.content:
            raise VoiceSynthesisError("Piper service returned empty audio")
        return bytes(response.content)
