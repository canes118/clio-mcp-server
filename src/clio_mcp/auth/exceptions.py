class ClioAuthError(Exception):
    """Base class for all Clio authentication errors."""


class ClioConfigError(ClioAuthError):
    """Missing or invalid configuration (e.g. no client_id in env)."""


class ClioTokenError(ClioAuthError):
    """Base class for token-related errors."""


class ClioTokenNotFoundError(ClioTokenError):
    """No tokens found on disk; OAuth bootstrap flow needed."""


class ClioTokenRefreshError(ClioTokenError):
    """Token refresh call to Clio failed."""


class ClioTokenFileCorruptError(ClioTokenError):
    """Token file exists but cannot be parsed."""
