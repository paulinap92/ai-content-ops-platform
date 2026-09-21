from fastapi import status


class APIException(Exception):
    def __init__(
            self,
            message: str,
            status_code: int = 400,
            error_code: str = "error"
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(message)


class NotFoundException(APIException):
    """404 - artykul o podanym thread_id nie istnieje"""

    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message, status.HTTP_404_NOT_FOUND, "not_found")


class ConflictException(APIException):
    """409 - artykul jest przetwarzany. Retry"""

    def __init__(self, message: str = "Conflict") -> None:
        super().__init__(message, status.HTTP_409_CONFLICT, "conflict")


class BusinessRuleException(APIException):
    """422 - naruszenie reguły biznesowej"""

    def __init__(self, message: str) -> None:
        super().__init__(message, status.HTTP_422_UNPROCESSABLE_ENTITY, "business_rule_violation")


class AgentException(APIException):
    """500 - wewnetrzny blad grafu (LLM timeout, Tavily, I/O"""

    def __init__(self, message: str = "Agent processing error") -> None:
        super().__init__(message, status.HTTP_500_INTERNAL_SERVER_ERROR, "agent_error")
