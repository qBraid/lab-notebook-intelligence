# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

from typing import Any
from notebook_intelligence.api import ChatModel, EmbeddingModel, InlineCompletionModel, LLMProvider, CancelToken, ChatResponse, CompletionContext
from notebook_intelligence.github_copilot import completions, inline_completions

class GitHubCopilotChatModel(ChatModel):
    @property
    def id(self) -> str:
        return "gpt-4o"
    
    @property
    def name(self) -> str:
        return "gpt-4o"
    
    @property
    def context_window(self) -> int:
        return 128000

    def completions(self, messages: list[dict], tools: list[dict] = None, response: ChatResponse = None, cancel_token: CancelToken = None, options: dict = {}) -> Any:
        return completions(messages, tools, response, cancel_token, options)

class GitHubCopilotInlineCompletionModel(InlineCompletionModel):
    @property
    def id(self) -> str:
        return "copilot-codex"
    
    @property
    def name(self) -> str:
        return "copilot-codex"
    
    @property
    def context_window(self) -> int:
        return 4096

    def inline_completions(self, prefix, suffix, language, filename, context: CompletionContext, cancel_token: CancelToken) -> str:
        return inline_completions(prefix, suffix, language, filename, context, cancel_token)

class GitHubCopilotLLMProvider(LLMProvider):
    def __init__(self):
        self._chat_model = GitHubCopilotChatModel(self)
        self._inline_completion_model = GitHubCopilotInlineCompletionModel(self)

    @property
    def id(self) -> str:
        return "github-copilot"
    
    @property
    def name(self) -> str:
        return "GitHub Copilot"

    @property
    def chat_models(self) -> list[ChatModel]:
        return [self._chat_model]
    
    @property
    def inline_completion_models(self) -> list[InlineCompletionModel]:
        return [self._inline_completion_model]
    
    @property
    def embedding_models(self) -> list[EmbeddingModel]:
        return []
