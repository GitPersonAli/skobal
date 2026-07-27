"""Expected, user-facing Skobal errors."""


class SkobalError(Exception):
    """Base class for errors that should be shown without a traceback."""


class StateError(SkobalError):
    """The managed-install manifest cannot be trusted or updated."""


class ConflictError(SkobalError):
    """An install destination cannot be changed safely."""


class SyncError(SkobalError):
    """A synchronization transaction failed."""


class GitError(SkobalError):
    """A safe git operation failed."""

