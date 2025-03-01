# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import json
from typing import Any
from notebook_intelligence.api import ChatModel, EmbeddingModel, InlineCompletionModel, LLMProvider, CancelToken, ChatResponse, CompletionContext, LLMProviderProperty
import litellm

class OpenAICompatibleChatModel(ChatModel):
    def __init__(self, provider: "OpenAICompatibleLLMProvider"):
        super().__init__(provider)
        self._provider = provider
        self._properties = [
            LLMProviderProperty("model_id", "Model", "Model", "", False),
            LLMProviderProperty("base_url", "Base URL", "Base URL", "", False),
            LLMProviderProperty("api_key", "API key", "API key", "", True),
        ]

    @property
    def id(self) -> str:
        return "openai-compatible-chat-model"
    
    @property
    def name(self) -> str:
        return self.get_property("model_id").value
    
    @property
    def context_window(self) -> int:
        return 4096

    def completions(self, messages: list[dict], tools: list[dict] = None, response: ChatResponse = None, cancel_token: CancelToken = None, options: dict = {}) -> Any:
        stream = response is not None
        model_id = self.get_property("model_id").value
        base_url = self.get_property("base_url").value
        api_key = self.get_property("api_key").value
        litellm_resp = litellm.completion(
            model=model_id,
            messages=messages.copy(),
            tools=tools,
            tool_choice=options.get("tool_choice", None),
            api_base=base_url,
            api_key=api_key,
            stream=stream,
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
        self._properties = [
            LLMProviderProperty("model_id", "Model", "Model", "", False),
            LLMProviderProperty("base_url", "Base URL", "Base URL", "", False),
            LLMProviderProperty("api_key", "API key", "API key", "", True),
        ]

    @property
    def id(self) -> str:
        return "openai-compatible-inline-completion-model"
    
    @property
    def name(self) -> str:
        return "Inline Completion Model"
    
    @property
    def context_window(self) -> int:
        return 4096

    def inline_completions(self, prefix, suffix, language, filename, context: CompletionContext, cancel_token: CancelToken) -> str:
        model_id = self.get_property("model_id").value
        base_url = self.get_property("base_url").value
        api_key = self.get_property("api_key").value
        # TODO: remove this and check if suffix parameter is standardized
        prompt = f"# the code below is written in {language}\n{prefix}"
        litellm_resp = litellm.completion(
            model=model_id,
            prompt=prompt,
            suffix=suffix,
            stream=False,
            api_base=base_url,
            api_key=api_key,
        )

        return litellm_resp.choices[0].message.content

class OpenAICompatibleLLMProvider(LLMProvider):
    def __init__(self):
        super().__init__()
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
