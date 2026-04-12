"""Auth package — access control + analytics for the swimming app."""

from auth.guard import require_auth, get_current_user, ROLE_LEVEL, ROLE_LABEL

__all__ = ["require_auth", "get_current_user", "ROLE_LEVEL", "ROLE_LABEL"]
