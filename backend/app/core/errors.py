from dataclasses import dataclass


@dataclass
class ServiceError(Exception):
    code: str
    message: str
    status_code: int = 400
    details: dict | None = None
    user_message: str | None = None
    retryable: bool = False

    def to_detail(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "user_message": self.user_message or self.message,
            "details": self.details or {},
            "retryable": self.retryable,
        }


class ConfigurationError(ServiceError):
    def __init__(self, message: str, code: str = "CONFIGURATION_ERROR", details: dict | None = None) -> None:
        super().__init__(code=code, message=message, status_code=503, details=details, retryable=False)


class DependencyUnavailableError(ServiceError):
    def __init__(
        self,
        message: str,
        code: str = "DEPENDENCY_UNAVAILABLE",
        details: dict | None = None,
        retryable: bool = True,
    ) -> None:
        super().__init__(code=code, message=message, status_code=503, details=details, retryable=retryable)


class IndexIncompatibleError(ServiceError):
    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(code="INDEX_INCOMPATIBLE", message=message, status_code=409, details=details)


class DuplicateDocumentError(ServiceError):
    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(code="DUPLICATE_DOCUMENT", message=message, status_code=409, details=details)
