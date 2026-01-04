"""
Throttle classes that log blocked requests for audit visibility.
"""
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle, ScopedRateThrottle

from .auth_logging import log_rate_limit_triggered


class LoggedAnonRateThrottle(AnonRateThrottle):
    """
    Anonymous throttle that logs blocked requests.
    """

    def allow_request(self, request, view):
        # Store request for use in throttle_failure
        self._request = request
        self._view = view
        return super().allow_request(request, view)

    def throttle_failure(self):
        log_rate_limit_triggered(request=getattr(self, '_request', None),
                                 scope=self.scope,
                                 blocked=True)
        return super().throttle_failure()


class LoggedUserRateThrottle(UserRateThrottle):
    """
    Authenticated-user throttle that logs blocked requests.
    """

    def allow_request(self, request, view):
        # Store request for use in throttle_failure
        self._request = request
        self._view = view
        return super().allow_request(request, view)

    def throttle_failure(self):
        log_rate_limit_triggered(request=getattr(self, '_request', None),
                                 scope=self.scope,
                                 blocked=True)
        return super().throttle_failure()


class LoggedScopedRateThrottle(ScopedRateThrottle):
    """
    Scoped throttle that logs blocked requests.
    """

    def allow_request(self, request, view):
        # Store request for use in throttle_failure
        self._request = request
        self._view = view
        return super().allow_request(request, view)

    def throttle_failure(self):
        log_rate_limit_triggered(request=getattr(self, '_request', None),
                                 scope=self.scope,
                                 blocked=True)
        return super().throttle_failure()
