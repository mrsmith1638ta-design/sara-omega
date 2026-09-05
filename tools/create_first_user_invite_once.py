from __future__ import annotations

import json
import os
from pathlib import Path

from app.user_identity import IdentityStoreError, UserIdentityStore

OUTBOX_NAME = "sara_first_user_invite.json"
REQUIRED_FIELDS = ("enrollment_id", "enrollment_url", "expires_at")


def _outbox_path() -> Path:
    data_dir = Path(os.getenv("SARA_DATA_DIR", "./data")).expanduser()
    data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    return data_dir / OUTBOX_NAME


def _validate_existing(path: Path) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IdentityStoreError("first_user_invitation_outbox_invalid") from exc
    if not isinstance(payload, dict) or any(not payload.get(field) for field in REQUIRED_FIELDS):
        raise IdentityStoreError("first_user_invitation_outbox_invalid")


def _write_private_json(path: Path, payload: dict[str, str]) -> None:
    temp = path.with_name(path.name + ".tmp")
    rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    try:
        temp.write_text(rendered, encoding="utf-8")
        try:
            os.chmod(temp, 0o600)
        except OSError:
            pass
        os.replace(temp, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    except OSError as exc:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        raise IdentityStoreError("first_user_invitation_outbox_write_failed") from exc


def main() -> int:
    path = _outbox_path()
    if path.exists():
        _validate_existing(path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        print("SARA first-user invitation ready.")
        return 0

    base_url = os.getenv("SARA_PUBLIC_BASE_URL", "").strip()
    if not base_url:
        raise IdentityStoreError("sara_public_base_url_required")

    store = UserIdentityStore.from_env(required=True)
    if store is None:
        raise IdentityStoreError("identity_store_unavailable")
    invitation = store.create_invitation(base_url=base_url)
    _write_private_json(
        path,
        {
            "enrollment_id": invitation.enrollment_id,
            "enrollment_url": invitation.enrollment_url,
            "expires_at": invitation.expires_at,
        },
    )
    print("SARA first-user invitation ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
