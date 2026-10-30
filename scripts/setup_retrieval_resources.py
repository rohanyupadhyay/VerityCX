"""Install the reviewed WordNet archive; all model packages come from uv's lock."""

import argparse
import os
import urllib.request
from hashlib import sha256

from veritycx.knowledge.resources import (
    WORDNET_PATH,
    ResourceError,
    resource_manifest,
    verify_resources,
)


def main() -> int:
    """Acquire only a pinned archive during explicit setup, or check without networking."""
    parser = argparse.ArgumentParser(description="Install/check pinned retrieval language data")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        if not args.check and not WORDNET_PATH.exists():
            asset = resource_manifest()["wordnet"]
            if not isinstance(asset, dict):
                raise ResourceError("nlp_resources_unavailable")
            url = str(asset["url"])
            if not url.startswith("https://raw.githubusercontent.com/nltk/nltk_data/"):
                raise ResourceError("nlp_resources_unavailable")
            with urllib.request.urlopen(url, timeout=45) as response:  # noqa: S310 - fixed HTTPS owner.
                raw = response.read(32 * 1024 * 1024 + 1)
            if len(raw) > 32 * 1024 * 1024 or sha256(raw).hexdigest() != asset["sha256"]:
                raise ResourceError("nlp_resources_unavailable")
            WORDNET_PATH.parent.mkdir(parents=True, exist_ok=True)
            temporary = WORDNET_PATH.with_suffix(".pending")
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(raw)
            temporary.replace(WORDNET_PATH)
        verify_resources()
    except Exception:
        print("nlp_resources_unavailable")
        return 1
    print("nlp_resources_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
