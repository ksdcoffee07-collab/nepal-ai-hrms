from urllib.parse import urlsplit

from django.conf import settings
from django.http import HttpResponseForbidden
from django.urls import Resolver404, resolve
from django.utils.translation import gettext as _

from base.dashboard_roles import resolve_home_role


_EMPLOYEE_ROUTE_METHODS = {
    "home-page": {"GET", "HEAD"},
    "ess": {"GET", "HEAD"},
    "ess-dashboard": {"GET", "HEAD"},
    "clock-in": {"GET"},
    "clock-out": {"GET"},
    "login": {"GET", "POST"},
    "logout": {"GET", "POST"},
    "change-password": {"GET", "POST"},
    "two-factor": {"GET", "POST"},
    "send-otp": {"GET", "POST"},
    "javascript-catalog": {"GET", "HEAD"},
}


class EmployeeAttendanceAccessMiddleware:
    """Limit ordinary employee web sessions to attendance and account access."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        static_path = urlsplit(settings.STATIC_URL).path
        if static_path and request.method in {"GET", "HEAD"}:
            if not static_path.startswith("/"):
                static_path = f"/{static_path}"
            if not static_path.endswith("/"):
                static_path += "/"
            if request.path_info.startswith(static_path):
                return self.get_response(request)

        if (
            not request.user.is_authenticated
            or resolve_home_role(request) != "employee"
        ):
            return self.get_response(request)

        try:
            route_name = resolve(request.path_info).url_name
        except Resolver404:
            return self._forbidden()

        if request.method in _EMPLOYEE_ROUTE_METHODS.get(route_name, set()):
            return self.get_response(request)
        return self._forbidden()

    @staticmethod
    def _forbidden():
        return HttpResponseForbidden(
            _("Employee accounts are limited to attendance and account access.")
        )
