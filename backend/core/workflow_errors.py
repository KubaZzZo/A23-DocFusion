"""Shared workflow exceptions for API/UI orchestration."""


class WorkflowError(Exception):
    """Base workflow error."""


class WorkflowNotFoundError(WorkflowError):
    """Requested workflow resource was not found."""


class WorkflowValidationError(WorkflowError):
    """Workflow input or state is invalid."""
