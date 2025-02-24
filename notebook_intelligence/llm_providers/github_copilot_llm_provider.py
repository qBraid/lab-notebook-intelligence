# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

from typing import Any
from notebook_intelligence.api import ChatModel, EmbeddingModel, InlineCompletionModel, LLMProvider, CancelToken, ChatResponse, CompletionContext
from notebook_intelligence.github_copilot import completions, inline_completions

class GitHubCopilotChatModel(ChatModel):
    def __init__(self, provider: LLMProvider, model_id: str):
        super().__init__(provider)
        self._model_id = model_id

    @property
    def id(self) -> str:
        return self._model_id
    
    @property
    def name(self) -> str:
        return self._model_id
    
    @property
    def context_window(self) -> int:
        return 128000

    def completions(self, messages: list[dict], tools: list[dict] = None, response: ChatResponse = None, cancel_token: CancelToken = None, options: dict = {}) -> Any:
        return completions(self._model_id, messages, tools, response, cancel_token, options)

class GitHubCopilotInlineCompletionModel(InlineCompletionModel):
    def __init__(self, provider: LLMProvider, model_id: str):
        super().__init__(provider)
        self._model_id = model_id

    @property
    def id(self) -> str:
        return self._model_id
    
    @property
    def name(self) -> str:
        return self._model_id
    
    @property
    def context_window(self) -> int:
        return 4096

    def inline_completions(self, prefix, suffix, language, filename, context: CompletionContext, cancel_token: CancelToken) -> str:
        return inline_completions(self._model_id, prefix, suffix, language, filename, context, cancel_token)

class GitHubCopilotLLMProvider(LLMProvider):
    def __init__(self):
        self._chat_model_gpt4o = GitHubCopilotChatModel(self, "gpt-4o")
        self._inline_completion_model_codex = GitHubCopilotInlineCompletionModel(self, "copilot-codex")
        self._inline_completion_model_gpt4o = GitHubCopilotInlineCompletionModel(self, "gpt-4o-copilot")

    @property
    def id(self) -> str:
        return "github-copilot"
    
    @property
    def name(self) -> str:
        return "GitHub Copilot"

    @property
    def chat_models(self) -> list[ChatModel]:
        return [self._chat_model_gpt4o]
    
    @property
    def inline_completion_models(self) -> list[InlineCompletionModel]:
        return [self._inline_completion_model_codex, self._inline_completion_model_gpt4o]
    
    @property
    def embedding_models(self) -> list[EmbeddingModel]:
        return []
