"""Check server-provisioned identities, disabled tokens and non-overwriting credentials."""

from pathlib import Path

import pytest

from veritycx.service.auth import AuthError, authenticate, init_demo, load_principals


def test_two_owners_and_safe_failures(tmp_path: Path) -> None:
    """High-entropy credentials select distinct server owners and cannot be overwritten."""
    files = init_demo(tmp_path)
    principals = load_principals(files[0])
    first = files[1].read_text().strip()
    second = files[2].read_text().strip()
    assert len(first) >= 43 and len(second) >= 43
    assert authenticate("Bearer " + first, principals) != authenticate(
        "Bearer " + second, principals
    )
    with pytest.raises(AuthError, match="credential_exists"):
        init_demo(tmp_path)
    for header in [None, "", "Bearer forged", "Basic " + first]:
        with pytest.raises(AuthError, match="unauthorized"):
            authenticate(header, principals)
    disabled = tuple(p.model_copy(update={"enabled": False}) for p in principals)
    with pytest.raises(AuthError, match="unauthorized"):
        authenticate("Bearer " + first, disabled)
