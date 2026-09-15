from creator.integrations.gemini.image_generator import (
    GeminiImageGenerationRequest,
    GeminiImageGenerationResult,
)


class FakeGeminiImageGenerator:
    def __init__(self, image_bytes: bytes) -> None:
        self.image_bytes = image_bytes
        self.requests: list[GeminiImageGenerationRequest] = []

    def generate(self, request: GeminiImageGenerationRequest) -> GeminiImageGenerationResult:
        self.requests.append(request)
        return GeminiImageGenerationResult(
            image_bytes=self.image_bytes,
            mime_type="image/png",
            width=1,
            height=1,
            model=request.model or "fake-gemini-image",
            prompt=request.prompt,
            metadata={"provider": "fake-gemini"},
        )
