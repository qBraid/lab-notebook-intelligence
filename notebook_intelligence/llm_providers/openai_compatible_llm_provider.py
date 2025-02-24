# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import json
from typing import Any
from notebook_intelligence.api import ChatModel, EmbeddingModel, InlineCompletionModel, LLMProvider, CancelToken, ChatResponse, CompletionContext
import litellm

class OpenAICompatibleChatModel(ChatModel):
    def __init__(self, provider: "OpenAICompatibleLLMProvider"):
        super().__init__(provider)
        self._provider = provider

    @property
    def id(self) -> str:
        return "chat-model"
    
    @property
    def name(self) -> str:
        return "Chat Model"
    
    @property
    def context_window(self) -> int:
        return 4096

    def completions(self, messages: list[dict], tools: list[dict] = None, response: ChatResponse = None, cancel_token: CancelToken = None, options: dict = {}) -> Any:
        stream = response is not None
        litellm_resp = litellm.completion(
            model=self._provider.chat_model_id,
            messages=messages.copy(),
            tools=tools,
            tool_choice=options.get("tool_choice", None),
            api_base=self._provider.chat_model_base_url,
            api_key=self._provider.chat_model_api_key,
            stream=stream
        )

        if stream:
            for chunk in litellm_resp:
                response.stream({
                        "choices": [{
                            "delta": {
                                "role": chunk.choices[0].delta.role,
                                "content": chunk.choices[0].delta.content
                            }
                        }]
                    })
            response.finish()
            return
        else:
            json_resp = json.loads(litellm_resp.model_dump_json())
            return json_resp
    
class OpenAICompatibleInlineCompletionModel(InlineCompletionModel):
    def __init__(self, provider: "OpenAICompatibleLLMProvider"):
        super().__init__(provider)
        self._provider = provider

    @property
    def id(self) -> str:
        return "inline-completion-model"
    
    @property
    def name(self) -> str:
        return "Inline Completion Model"
    
    @property
    def context_window(self) -> int:
        return 4096

    def inline_completions(self, prefix, suffix, language, filename, context: CompletionContext, cancel_token: CancelToken) -> str:
        prompt = f"# the code below is written in {language}\n{prefix}"
        litellm_resp = litellm.completion(
            model=self._provider.inline_completion_model_id,
            prompt=prompt,
            suffix=suffix,
            stream=False,
            api_base=self._provider.inline_completion_model_base_url,
            api_key=self._provider.inline_completion_model_api_key,
        )

        return litellm_resp.choices[0].message.content

class OpenAICompatibleLLMProvider(LLMProvider):
    def __init__(self):
        super().__init__()
        self.chat_model_id = "gpt-4o"
        self.chat_model_base_url = None
        self.chat_model_api_key = None
        self.inline_completion_model_id = "gpt-3.5-turbo-instruct"
        self.inline_completion_model_base_url = None
        self.inline_completion_model_api_key = None
        self._chat_model = OpenAICompatibleChatModel(self)
        self._inline_completion_model = OpenAICompatibleInlineCompletionModel(self)

    @property
    def id(self) -> str:
        return "openai-compatible"
    
    @property
    def name(self) -> str:
        return "OpenAI Compatible"

    @property
    def chat_models(self) -> list[ChatModel]:
        return [self._chat_model]
    
    @property
    def inline_completion_models(self) -> list[InlineCompletionModel]:
        return [self._inline_completion_model]
    
    @property
    def embedding_models(self) -> list[EmbeddingModel]:
        return []
