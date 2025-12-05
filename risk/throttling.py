"""
Throttle classes that log blocked requests for audit visibility.
"""
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle, ScopedRateThrottle

from .auth_logging import log_rate_limit_triggered


class LoggedAnonRateThrottle(AnonRateThrottle):
    """
    Anonymous throttle that logs blocked requests.
    """

    def throttle_failure(self, request, view):
        log_rate_limit_triggered(request=request,
                                 scope=self.scope,
                                 blocked=True)
        return super().throttle_failure(request, view)


class LoggedUserRateThrottle(UserRateThrottle):
    """
    Authenticated-user throttle that logs blocked requests.
    """

    def throttle_failure(self, request, view):
        log_rate_limit_triggered(request=request,
                                 scope=self.scope,
                                 blocked=True)
        return super().throttle_failure(request, view)


class LoggedScopedRateThrottle(ScopedRateThrottle):
    """
    Scoped throttle that logs blocked requests.
    """

    def throttle_failure(self, request, view):
        log_rate_limit_triggered(request=request,
                                 scope=self.scope,
                                 blocked=True)
        return super().throttle_failure(request, view)
