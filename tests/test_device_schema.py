import pytest
from pydantic import ValidationError

from app.models.device import DeviceType
from app.schemas.device import DeviceRegisterRequest


def test_fingerprint_is_normalized_to_lowercase() -> None:
    request = DeviceRegisterRequest(
        fingerprint_hash="A" * 64,
        type=DeviceType.WITNESS,
        platform="android",
        app_version="1.0.0",
    )

    assert request.fingerprint_hash == "a" * 64


@pytest.mark.parametrize(
    "fingerprint",
    ["a" * 63, "a" * 65, "z" * 64, "not-a-sha256"],
)
def test_invalid_fingerprint_is_rejected(fingerprint: str) -> None:
    with pytest.raises(ValidationError):
        DeviceRegisterRequest(
            fingerprint_hash=fingerprint,
            type=DeviceType.WITNESS,
            platform="android",
            app_version="1.0.0",
        )
