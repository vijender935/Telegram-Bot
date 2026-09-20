"""Application-level exception taxonomy.

Handlers can catch BotError subclasses and keep provider details out of user-facing messages.
"""


class BotError(Exception):
    """Base class for expected, user-safe application failures."""


class ConfigurationError(BotError):
    pass


class AuthenticationError(BotError):
    pass


class AuthorizationError(BotError):
    pass


class RateLimitError(BotError):
    pass


class AIServiceError(BotError):
    pass


class TelegramServiceError(BotError):
    pass


class MediaError(BotError):
    pass


class VaultError(BotError):
    pass


class StorageError(BotError):
    pass
