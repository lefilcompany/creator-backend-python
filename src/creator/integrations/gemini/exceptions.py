class GeminiProviderError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class GeminiAuthenticationError(GeminiProviderError):
    pass


class GeminiQuotaError(GeminiProviderError):
    pass


class GeminiTimeoutError(GeminiProviderError):
    pass


class GeminiBlockedContentError(GeminiProviderError):
    pass


class GeminiTransientError(GeminiProviderError):
    pass


class GeminiInvalidResponseError(GeminiProviderError):
    pass
