import asyncio
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.core.security import (
    create_device_token,
    decode_device_token,
    get_current_device_id,
    verify_device_id,
)


def test_device_token_round_trip() -> None:
    device_id = uuid4()
    assert decode_device_token(create_device_token(device_id)) == device_id


def test_invalid_device_token_is_rejected() -> None:
    with pytest.raises(HTTPException) as error:
        decode_device_token("not-a-token")
    assert error.value.status_code == 401


def test_device_id_spoofing_is_rejected() -> None:
    with pytest.raises(HTTPException) as error:
        verify_device_id(uuid4(), uuid4())
    assert error.value.status_code == 403


def test_missing_bearer_token_is_rejected_when_auth_is_enabled() -> None:
    previous = settings.AUTH_REQUIRED
    settings.AUTH_REQUIRED = True
    try:
        with pytest.raises(HTTPException) as error:
            asyncio.run(get_current_device_id(None))
        assert error.value.status_code == 401
    finally:
        settings.AUTH_REQUIRED = previous
