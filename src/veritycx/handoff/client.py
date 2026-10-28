"""Make bounded privileged Chatwoot API requests without retries or raw diagnostics."""

from dataclasses import dataclass
from uuid import UUID

import httpx

from veritycx.conversations.models import parse_json
from veritycx.handoff.configuration import ChatwootConfiguration
from veritycx.handoff.events import object_value, positive_id


class ChatwootRemoteError(ValueError):
    """Expose a safe category for remote outages and invalid response shapes."""


@dataclass(frozen=True)
class RemoteConversation:
    """Represent only the ownership information needed for publication decisions."""

    status: str
    bot_owned: bool


class ChatwootClient:
    """Use one trusted origin and account; never follow redirects or retry mutations."""

    def __init__(self, configuration: ChatwootConfiguration, http: httpx.AsyncClient) -> None:
        """Retain the bounded client and trusted server configuration."""
        self.config = configuration
        self.http = http

    async def request(
        self,
        method: str,
        external_id: int,
        suffix: str = "",
        body: dict[str, object] | None = None,
        params: dict[str, int] | None = None,
    ) -> dict[str, object]:
        """Bound response bytes and convert every provider failure to a fixed safe category."""
        url = (
            f"{self.config.base_url}/api/v1/accounts/{self.config.account_id}"
            f"/conversations/{positive_id(external_id)}{suffix}"
        )
        # Pinned AgentBot authorization permits messages#create but not messages#index.
        # Read/reconciliation requests require an account user; publication must retain
        # AgentBot credentials so Chatwoot records the correct message sender.
        token = (
            self.config.bot_token
            if method == "POST" and suffix == "/messages"
            else self.config.api_token
        )
        try:
            async with self.http.stream(
                method,
                url,
                json=body,
                params=params,
                headers={"api_access_token": token.get_secret_value()},
                follow_redirects=False,
                timeout=10,
            ) as response:
                if response.status_code < 200 or response.status_code >= 300:
                    raise ValueError
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(content) + len(chunk) > 1048576:
                        raise ValueError
                    content.extend(chunk)
                return object_value(parse_json(bytes(content)))
        except (httpx.HTTPError, ValueError, TypeError, RecursionError):
            raise ChatwootRemoteError("chatwoot_unavailable") from None

    async def conversation(self, external_id: int) -> RemoteConversation:
        """Read authoritative current status and inbox, including human assignments."""
        data = await self.request("GET", external_id)
        try:
            if positive_id(data.get("id")) != external_id:
                raise ValueError
            if positive_id(data.get("inbox_id")) != self.config.inbox_id:
                raise ValueError
            status = data.get("status")
            if status not in ("pending", "open", "resolved", "snoozed"):
                raise ValueError
            meta = object_value(data.get("meta"))
            assignee = meta.get("assignee")
            # Customer resolve/reopen can yield pending with no assignee. Only an actual
            # AgentBot assignment establishes bot authority, including after human handoff.
            bot_owned = (
                status == "pending"
                and meta.get("assignee_type") == "AgentBot"
                and isinstance(assignee, dict)
                and type(assignee.get("id")) is int
                and 1 <= assignee["id"] <= 2**63 - 1
            )
            return RemoteConversation(str(status), bot_owned)
        except ValueError:
            raise ChatwootRemoteError("chatwoot_unavailable") from None

    async def open(self, external_id: int) -> None:
        """Set a specific status, so retries cannot toggle ownership back to automation."""
        await self.request("POST", external_id, "/toggle_status", {"status": "open"})

    async def message(self, external_id: int, marker: UUID, content: str, *, private: bool) -> int:
        """Post once with a persistent correlation marker for uncertain delivery reconciliation."""
        data = await self.request(
            "POST",
            external_id,
            "/messages",
            {
                "content": content,
                "message_type": "outgoing",
                "private": private,
                "content_attributes": {"veritycx_turn_id": str(marker)},
            },
        )
        try:
            return positive_id(data.get("id"))
        except ValueError:
            raise ChatwootRemoteError("chatwoot_unavailable") from None

    async def find_message(self, external_id: int, marker: UUID) -> int | None:
        """Search at most 20 pages for a durable marker; absence never authorizes reposting."""
        before: int | None = None
        for _ in range(20):
            data = await self.request(
                "GET", external_id, "/messages", params={"before": before} if before else None
            )
            messages = data.get("payload")
            if not isinstance(messages, list):
                raise ChatwootRemoteError("chatwoot_unavailable")
            ids: list[int] = []
            for value in messages:
                try:
                    message = object_value(value)
                    message_id = positive_id(message.get("id"))
                    ids.append(message_id)
                    attributes = message.get("content_attributes")
                    if isinstance(attributes, dict) and attributes.get("veritycx_turn_id") == str(
                        marker
                    ):
                        return message_id
                except ValueError:
                    raise ChatwootRemoteError("chatwoot_unavailable") from None
            if not ids or (before is not None and min(ids) >= before):
                return None
            before = min(ids)
        return None
