"""Bridge verified Chatwoot events to durable isolated support conversations."""

from veritycx.handoff.configuration import ChatwootConfiguration, load_chatwoot_configuration

__all__ = ["ChatwootConfiguration", "load_chatwoot_configuration"]
