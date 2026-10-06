import logging

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404, JsonResponse
from rest_framework import exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from .constants import ErrorCode

logger = logging.getLogger(__name__)


class ApiError(Exception):
    status_code = 500
    error_code = ErrorCode.INTERNAL_ERROR
    message = "Internal error"

    def __init__(self, message: str | None = None, details: dict | None = None):
        self.message = message or self.message
        self.details = details or {}
        super().__init__(self.message)


class RequiredFieldsMissing(ApiError):
    status_code = 406
    error_code = ErrorCode.REQUIRED_FIELDS_MISSING
    message = "Required fields are missing"


class ValidationFailed(ApiError):
    status_code = 400
    error_code = ErrorCode.VALIDATION_ERROR
    message = "Validation failed"


class FactoryNotFound(ApiError):
    status_code = 404
    error_code = ErrorCode.FACTORY_NOT_FOUND
    message = "Factory not found"


class AuthorMismatch(ApiError):
    status_code = 403
    error_code = ErrorCode.AUTHOR_MISMATCH
    message = "author must match the authenticated user"


class NoPermittedGroup(ApiError):
    status_code = 403
    error_code = ErrorCode.NO_PERMITTED_GROUP
    message = "user has no role permitted to save work volume"


class TsDBUnavailable(ApiError):
    status_code = 503
    error_code = ErrorCode.TSDB_UNAVAILABLE
    message = "Time-series database is unavailable"


def _body(code: ErrorCode, message: str, details) -> dict:
    return {"errorCode": int(code), "message": message, "details": details}


def not_found_view(request, exception=None):
    """JSON 404 for URLs outside the API (the body follows the common error format)."""
    return JsonResponse(_body(ErrorCode.NOT_FOUND, "Not found", {}), status=404)


def api_exception_handler(exc, context):
    if isinstance(exc, ApiError):
        return Response(_body(exc.error_code, exc.message, exc.details), status=exc.status_code)

    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()

    if not isinstance(exc, exceptions.APIException):
        logger.exception("Unhandled exception", exc_info=exc)
        return Response(_body(ErrorCode.INTERNAL_ERROR, "Internal error", {}), status=500)

    # Let DRF compute headers (WWW-Authenticate, Retry-After) and status code.
    drf_response = drf_exception_handler(exc, context)
    headers = dict(drf_response.headers) if drf_response is not None else {}
    headers.pop("Content-Type", None)
    message = str(exc.detail) if not isinstance(exc.detail, (list, dict)) else "Validation failed"

    if isinstance(exc, (exceptions.NotAuthenticated, exceptions.AuthenticationFailed)):
        status, code, details = 401, ErrorCode.NOT_AUTHENTICATED, {}
    elif isinstance(exc, exceptions.ParseError):
        status, code, details = 400, ErrorCode.VALIDATION_ERROR, {}
    elif isinstance(exc, exceptions.ValidationError):
        details = exc.detail if isinstance(exc.detail, dict) else {"non_field_errors": exc.detail}
        status, code = 400, ErrorCode.VALIDATION_ERROR
    elif isinstance(exc, exceptions.MethodNotAllowed):
        status, code, details = 405, ErrorCode.METHOD_NOT_ALLOWED, {}
    elif isinstance(exc, exceptions.UnsupportedMediaType):
        status, code, details = 415, ErrorCode.UNSUPPORTED_MEDIA_TYPE, {}
    elif isinstance(exc, exceptions.NotAcceptable):
        status, code, details = 406, ErrorCode.NOT_ACCEPTABLE, {}
    elif isinstance(exc, exceptions.PermissionDenied):
        # Business 403s are ApiError (902/903); this is a generic one, e.g. CSRF failure.
        status, code, details = 403, ErrorCode.FORBIDDEN, {}
    elif isinstance(exc, exceptions.NotFound):
        status, code, details = 404, ErrorCode.NOT_FOUND, {}
    else:
        status, code, details = exc.status_code, ErrorCode.INTERNAL_ERROR, {}

    headers = {k: v for k, v in headers.items() if k.lower() in ("www-authenticate", "retry-after")}
    return Response(_body(code, message, details), status=status, headers=headers)
