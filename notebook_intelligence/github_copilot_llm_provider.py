# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

from typing import Any
from notebook_intelligence.api import LLMProvider, CancelToken, ChatResponse, CompletionContext
from notebook_intelligence.github_copilot import completions, inline_completions

class GitHubCopilotLLMProvider(LLMProvider):
    def completions(self, messages: list[dict], tools: list[dict] = None, response: ChatResponse = None, cancel_token: CancelToken = None, options: dict = {}) -> Any:
        return completions(messages, tools, response, cancel_token, options)

    def inline_completions(self, prefix, suffix, language, filename, context: CompletionContext, cancel_token: CancelToken) -> str:
        return inline_completions(prefix, suffix, language, filename, context, cancel_token)
