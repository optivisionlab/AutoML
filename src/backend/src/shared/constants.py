# Standard Libraries
from enum import Enum


class ErrorCode(str, Enum):
    """
    A collection of system-wide error codes
    """
    BAD_REQUEST = "BAD_REQUEST"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"


class MessageResponse(str, Enum):
    """
    A collection of message in API response
    """
    SUCCESS = "Success"
    FAILED = "Failed"


class ProblemType(str):
    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    TIME_SERIES = "time_series"


class MapReduceMode(str):
    LOCAL = "local"
    CLUSTER = "cluster"
