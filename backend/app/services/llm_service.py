from app.services.providers import LLMProvider, get_llm_provider


class LLMService:
    def __init__(self, provider: LLMProvider | None = None) -> None:
        self.provider = provider or get_llm_provider()

    def is_configured(self) -> bool:
        return self.provider.is_configured()

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        return self.provider.complete(system_prompt=system_prompt, user_prompt=user_prompt)
