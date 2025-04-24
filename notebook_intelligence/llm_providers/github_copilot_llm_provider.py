# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

from typing import Any

import requests
from notebook_intelligence.api import ChatModel, EmbeddingModel, InlineCompletionModel, LLMProvider, CancelToken, ChatResponse, CompletionContext
from notebook_intelligence.github_copilot import generate_copilot_headers, completions, inline_completions
import logging

log = logging.getLogger(__name__)

GH_COPILOT_EXCLUDED_MODELS = set(["o1"])

class GitHubCopilotChatModel(ChatModel):
    def __init__(self, provider: LLMProvider, model_id: str, model_name: str, context_window: int, supports_tools: bool):
        super().__init__(provider)
        self._model_id = model_id
        self._model_name = model_name
        self._context_window = context_window
        self._supports_tools = supports_tools

    @property
    def id(self) -> str:
        return self._model_id
    
    @property
    def name(self) -> str:
        return self._model_name
    
    @property
    def context_window(self) -> int:
        return self._context_window

    @property
    def supports_tools(self) -> bool:
        return self._supports_tools

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
        self._chat_models = [
            GitHubCopilotChatModel(self, "gpt-4.1", "GPT-4.1", 128000, True),
            GitHubCopilotChatModel(self, "gpt-4o", "GPT-4o", 128000, True),
            GitHubCopilotChatModel(self, "o3-mini", "o3-mini", 200000, True),
            GitHubCopilotChatModel(self, "claude-3.5-sonnet", "Claude 3.5 Sonnet", 90000, True),
            GitHubCopilotChatModel(self, "claude-3.7-sonnet", "Claude 3.7 Sonnet", 200000, True),
            GitHubCopilotChatModel(self, "gemini-2.0-flash-001", "Gemini 2.0 Flash", 1000000, False),
            GitHubCopilotChatModel(self, "gemini-2.5-pro", "Gemini 2.5 Pro", 128000, True),
        ]
        self._inline_completion_model_gpt4o = GitHubCopilotInlineCompletionModel(self, "gpt-4o-copilot")
        self._inline_completion_model_codex = GitHubCopilotInlineCompletionModel(self, "copilot-codex")

    @property
    def id(self) -> str:
        return "github-copilot"
    
    @property
    def name(self) -> str:
        return "GitHub Copilot"

    @property
    def chat_models(self) -> list[ChatModel]:
        return self._chat_models
    
    @property
    def inline_completion_models(self) -> list[InlineCompletionModel]:
        return [self._inline_completion_model_gpt4o, self._inline_completion_model_codex]
    
    @property
    def embedding_models(self) -> list[EmbeddingModel]:
        return []

