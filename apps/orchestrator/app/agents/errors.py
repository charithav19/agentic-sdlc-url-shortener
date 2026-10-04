"""Classified provider failures; no implicit fallback or retry."""


class AgentProviderError(RuntimeError):
    code = "PROVIDER_ERROR"
    retryable = False


class AgentConfigurationError(AgentProviderError):
    code = "CONFIGURATION"


class AgentOutputError(AgentProviderError):
    code = "INVALID_OUTPUT"


class AgentToolDenied(AgentProviderError):
    code = "TOOL_DENIED"


class AgentBudgetExceeded(AgentProviderError):
    code = "MAX_TURNS"


class AgentTimeout(AgentProviderError):
    code = "TIMEOUT"
    retryable = True


class AgentTransientError(AgentProviderError):
    code = "TRANSIENT_PROVIDER_ERROR"
    retryable = True
