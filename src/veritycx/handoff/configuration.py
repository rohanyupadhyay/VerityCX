"""Load optional Chatwoot configuration without exposing privileged credentials."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from ipaddress import ip_address
from urllib.parse import urlsplit

from pydantic import SecretStr


class ChatwootConfigurationError(ValueError):
    """Expose a fixed configuration error without supplied settings."""


@dataclass(frozen=True)
class ChatwootConfiguration:
    """Keep private credentials out of dataclass diagnostics and browser responses."""

    base_url: str
    account_id: int
    inbox_id: int
    website_token: str = field(repr=False)
    api_token: SecretStr = field(repr=False)
    webhook_secret: SecretStr = field(repr=False)
    bot_token: SecretStr = field(repr=False)

    def public(self) -> dict[str, bool | str | None]:
        """Return only the browser's public widget bootstrap configuration."""
        return {"enabled": True, "base_url": self.base_url, "website_token": self.website_token}


def load_chatwoot_configuration(env: Mapping[str, str]) -> ChatwootConfiguration | None:
    """Disable only when every integration field is empty; reject partial or unsafe setup."""
    values = [
        env.get("VERITYCX_CHATWOOT_URL", "").strip(),
        env.get("VERITYCX_CHATWOOT_ACCOUNT_ID", "").strip(),
        env.get("VERITYCX_CHATWOOT_INBOX_ID", "").strip(),
        env.get("VERITYCX_CHATWOOT_WEBSITE_TOKEN", "").strip(),
        env.get("VERITYCX_CHATWOOT_API_TOKEN", "").strip(),
        env.get("VERITYCX_CHATWOOT_WEBHOOK_SECRET", "").strip(),
        env.get("VERITYCX_CHATWOOT_BOT_TOKEN", "").strip(),
    ]
    if not any(values):
        return None
    try:
        if not all(values):
            raise ValueError
        origin, account, inbox, website, token, secret, bot_token = values
        parsed = urlsplit(origin)
        host = parsed.hostname
        port = parsed.port
        loopback = host == "localhost"
        if host and not loopback:
            try:
                loopback = ip_address(host).is_loopback
            except ValueError:
                pass
        if (
            len(origin) > 2048
            or not host
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
            or "\\" in origin
            or any(character.isspace() for character in origin)
            or parsed.scheme not in ("http", "https")
            or (parsed.scheme == "http" and not loopback)
            or (port is not None and not 1 <= port <= 65535)
            or not account.isascii()
            or not account.isdecimal()
            or not inbox.isascii()
            or not inbox.isdecimal()
            or not 1 <= int(account) <= 2**63 - 1
            or not 1 <= int(inbox) <= 2**63 - 1
            or max(len(website), len(token), len(secret), len(bot_token)) > 4096
        ):
            raise ValueError
        return ChatwootConfiguration(
            base_url=origin.rstrip("/"),
            account_id=int(account),
            inbox_id=int(inbox),
            website_token=website,
            api_token=SecretStr(token),
            webhook_secret=SecretStr(secret),
            bot_token=SecretStr(bot_token),
        )
    except (ValueError, OverflowError):
        raise ChatwootConfigurationError("invalid_chatwoot_configuration") from None
