"""Backward-compatible import for the vault guard."""
from bot.application.vault_guard import VaultAttempt, VaultGuard

__all__ = ["VaultAttempt", "VaultGuard"]
