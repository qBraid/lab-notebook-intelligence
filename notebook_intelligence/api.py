# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import asyncio
import json
from typing import Any, Callable, Dict, Union
from dataclasses import asdict, dataclass
from enum import Enum
import uuid
from fuzzy_json import loads as fuzzy_json_loads
import logging

log = logging.getLogger(__name__)

class RequestDataType(str, Enum):
    ChatRequest = 'chat-request'
    ChatUserInput = 'chat-user-input'
    ClearChatHistory = 'clear-chat-history'
    RunUICommandResponse = 'run-ui-command-response'
    GenerateCode = 'generate-code'
    CancelChatRequest = 'cancel-chat-request'
    InlineCompletionRequest = 'inline-completion-request'
    CancelInlineCompletionRequest = 'cancel-inline-completion-request'

class BackendMessageType(str, Enum):
    StreamMessage = 'stream-message'
    StreamEnd = 'stream-end'
    RunUICommand = 'run-ui-command'

class ResponseStreamDataType(str, Enum):
    LLMRaw = 'llm-raw'
    Markdown = 'markdown'
    MarkdownPart = 'markdown-part'
    HTMLFrame = 'html-frame'
    Button = 'button'
    Anchor = 'anchor'
    Progress = 'progress'
    Confirmation = 'confirmation'

    def __str__(self) -> str:
        return self.value

class Signal:
    def __init__(self):
        self._listeners = []

    def connect(self, listener: Callable) -> None:
        self._listeners.append(listener)

    def disconnect(self, listener: Callable) -> None:
        self._listeners.remove(listener)

class SignalImpl(Signal):
    def __init__(self):
        super().__init__()

    def emit(self, *args, **kwargs) -> None:
        for listener in self._listeners:
            listener(*args, **kwargs)

class CancelToken:
    def __init__(self):
        self._cancellation_signal = Signal()
        self._cancellation_requested = False

    @property
    def is_cancel_requested(self) -> bool:
        return self._cancellation_requested

    @property
    def cancellation_signal(self) -> Signal:
        return self._cancellation_signal

@dataclass
class ChatRequest:
    host: 'Host' = None
    command: str = ''
    prompt: str = ''
    chat_history: list[dict] = None
    cancel_token: CancelToken = None

@dataclass
class ResponseStreamData:
    @property
    def data_type(self) -> ResponseStreamDataType:
        raise NotImplemented

@dataclass
class MarkdownData(ResponseStreamData):
    content: str = ''

    @property
    def data_type(self) -> ResponseStreamDataType:
        return ResponseStreamDataType.Markdown

@dataclass
class MarkdownPartData(ResponseStreamData):
    content: str = ''

    @property
    def data_type(self) -> ResponseStreamDataType:
        return ResponseStreamDataType.MarkdownPart

@dataclass
class HTMLFrameData(ResponseStreamData):
    source: str = ''
    height: int = 30

    @property
    def data_type(self) -> ResponseStreamDataType:
        return ResponseStreamDataType.HTMLFrame

@dataclass
class AnchorData(ResponseStreamData):
    uri: str = ''
    title: str = ''

    @property
    def data_type(self) -> ResponseStreamDataType:
        return ResponseStreamDataType.Anchor

@dataclass
class ButtonData(ResponseStreamData):
    title: str = ''
    commandId: str = ''
    args: Dict[str, str] = None

    @property
    def data_type(self) -> ResponseStreamDataType:
        return ResponseStreamDataType.Button

@dataclass
class ProgressData(ResponseStreamData):
    title: str = ''

    @property
    def data_type(self) -> ResponseStreamDataType:
        return ResponseStreamDataType.Progress

@dataclass
class ConfirmationData(ResponseStreamData):
    title: str = ''
    message: str = ''
    confirmArgs: dict = None
    cancelArgs: dict = None
    confirmLabel: str = None
    cancelLabel: str = None

    @property
    def data_type(self) -> ResponseStreamDataType:
        return ResponseStreamDataType.Confirmation

class ContextRequestType(Enum):
    InlineCompletion = 'inline-completion'
    NewPythonFile = 'new-python-file'
    NewNotebook = 'new-notebook'

class ContextType(Enum):
    Custom = 'custom'
    Provider = 'provider'
    CurrentFile = 'current-file'

@dataclass
class ContextRequest:
    type: ContextRequestType
    prefix: str = ''
    suffix: str = ''
    language: str = ''
    filename: str = ''
    participant: 'ChatParticipant' = None
    cancel_token: CancelToken = None

@dataclass
class ContextItem:
    type: ContextType
    content: str
    currentCellContents: dict = None
    filePath: str = None
    cellIndex: int = None
    startLine: int = None
    endLine: int = None

@dataclass
class CompletionContext:
    items: list[ContextItem]

class ChatResponse:
    def __init__(self):
        self._user_input_signal: SignalImpl = SignalImpl()
        self._run_ui_command_response_signal: SignalImpl = SignalImpl()
        self.participant_id = ''

    @property
    def message_id(self) -> str:
        raise NotImplemented

    def stream(self, data: ResponseStreamData, finish: bool = False) -> None:
        raise NotImplemented
    
    def finish(self) -> None:
        raise NotImplemented
    
    @property
    def user_input_signal(self) -> Signal:
        return self._user_input_signal

    def on_user_input(self, data: dict) -> None:
        self._user_input_signal.emit(data)

    @staticmethod
    async def wait_for_chat_user_input(response: 'ChatResponse', callback_id: str):
        resp = {"data": None}
        def _on_user_input(data: dict):
            if data['callback_id'] == callback_id:
                resp["data"] = data['data']

        response.user_input_signal.connect(_on_user_input)

        while True:
            if resp["data"] is not None:
                response.user_input_signal.disconnect(_on_user_input)
                return resp["data"]
            await asyncio.sleep(0.1)

    async def run_ui_command(self, command: str, args: dict = {}) -> None:
        raise NotImplemented
    
    @property
    def run_ui_command_response_signal(self) -> Signal:
        return self._run_ui_command_response_signal
    
    def on_run_ui_command_response(self, data: dict) -> None:
        self._run_ui_command_response_signal.emit(data)

    @staticmethod
    async def wait_for_run_ui_command_response(response: 'ChatResponse', callback_id: str):
        resp = {"result": None}
        def _on_ui_command_response(data: dict):
            if data['callback_id'] == callback_id:
                resp["result"] = data['result']

        response.run_ui_command_response_signal.connect(_on_ui_command_response)

        while True:
            if resp["result"] is not None:
                response.run_ui_command_response_signal.disconnect(_on_ui_command_response)
                return resp["result"]
            await asyncio.sleep(0.1)

@dataclass
class ToolPreInvokeResponse:
    message: str = None
    confirmationTitle: str = None
    confirmationMessage: str = None

@dataclass
class ChatCommand:
    name: str = ''
    description: str = ''

class Tool:
    @property
    def name(self) -> str:
        raise NotImplemented

    @property
    def title(self) -> str:
        raise NotImplemented
    
    @property
    def tags(self) -> list[str]:
        raise NotImplemented
    
    @property
    def description(self) -> str:
        raise NotImplemented
    
    @property
    def schema(self) -> dict:
        raise NotImplemented

    def pre_invoke(self, request: ChatRequest, tool_args: dict) -> Union[ToolPreInvokeResponse, None]:
        return None

    async def handle_tool_call(self, request: ChatRequest, response: ChatResponse, tool_context: dict, tool_args: dict) -> dict:
        raise NotImplemented

class ChatParticipant:
    @property
    def id(self) -> str:
        raise NotImplemented

    @property
    def name(self) -> str:
        raise NotImplemented

    @property
    def description(self) -> str:
        raise NotImplemented
    
    @property
    def icon_path(self) -> str:
        return None
    
    @property
    def commands(self) -> list[ChatCommand]:
        return []
    
    @property
    def tools(self) -> list[Tool]:
        return []

    @property
    def allowed_context_providers(self) -> set[str]:
        # any context provider can be used
        return set(["*"])

    async def handle_chat_request(self, request: ChatRequest, response: ChatResponse, options: dict = {}) -> None:
        raise NotImplemented
    
    async def handle_chat_request_with_tools(self, request: ChatRequest, response: ChatResponse, options: dict = {}, tool_context: dict = {}, tool_choice = 'auto') -> None:
        tools = self.tools

        messages = request.chat_history.copy()

        if len(tools) == 0:
            request.host.chat_model.completions(messages, tools=None, cancel_token=request.cancel_token, response=response)
            return

        openai_tools = [tool.schema for tool in tools]


        tool_call_rounds = []
        # TODO overrides options arg
        options = {'tool_choice': tool_choice}

        async def _tool_call_loop(tool_call_rounds: list):
            try:
                tool_response = request.host.chat_model.completions(messages, openai_tools, cancel_token=request.cancel_token, options=options)
                # after first call, set tool_choice to auto
                options['tool_choice'] = 'auto'

                if tool_response['choices'][0]['message'].get('tool_calls', None) is not None:
                    for tool_call in tool_response['choices'][0]['message']['tool_calls']:
                        tool_call_rounds.append(tool_call)
                elif tool_response['choices'][0]['message'].get('content', None) is not None:
                    response.stream(MarkdownData(tool_response['choices'][0]['message']['content']))

                messages.append(tool_response['choices'][0]['message'])

                had_tool_call = len(tool_call_rounds) > 0

                # handle first tool calls
                while len(tool_call_rounds) > 0:
                    tool_call = tool_call_rounds[0]
                    if "id" not in tool_call:
                        tool_call['id'] = uuid.uuid4().hex
                    tool_call_rounds = tool_call_rounds[1:]

                    tool_name = tool_call['function']['name']
                    tool_to_call = self._get_tool_by_name(tool_name)
                    if tool_to_call is None:
                        log.error(f"Tool not found: {tool_name}, args: {tool_call['function']['arguments']}")
                        response.stream(MarkdownData("Oops! Failed to find requested tool. Please try again with a different prompt."))
                        response.finish()
                        return

                    if type(tool_call['function']['arguments']) is dict:
                        args = tool_call['function']['arguments']
                    elif not tool_call['function']['arguments'].startswith('{'):
                        args = tool_call['function']['arguments']
                    else:
                        args = fuzzy_json_loads(tool_call['function']['arguments'])

                    tool_properties = tool_to_call.schema["function"]["parameters"]["properties"]
                    if type(args) is str:
                        if len(tool_properties) == 1 and tool_call['function']['arguments'] is not None:
                            tool_property = list(tool_properties.keys())[0]
                            args = {tool_property: args}
                        else:
                            args = {}

                    if len(tool_properties) != len(args):
                        response.stream(MarkdownData(f"Oops! There was a problem handling tool request. Please try again with a different prompt."))
                        response.finish()
                        return

                    tool_pre_invoke_response = tool_to_call.pre_invoke(request, args)
                    if tool_pre_invoke_response is not None:
                        if tool_pre_invoke_response.message is not None:
                            response.stream(MarkdownData(f"&#x2713; {tool_pre_invoke_response.message}..."))
                        if tool_pre_invoke_response.confirmationMessage is not None:
                            response.stream(ConfirmationData(
                                title=tool_pre_invoke_response.confirmationTitle,
                                message=tool_pre_invoke_response.confirmationMessage,
                                confirmArgs={"id": response.message_id, "data": { "callback_id": tool_call['id'], "data": {"confirmed": True}}},
                                cancelArgs={"id": response.message_id, "data": { "callback_id": tool_call['id'], "data": {"confirmed": False}}},
                            ))
                            user_input = await ChatResponse.wait_for_chat_user_input(response, tool_call['id'])
                            if user_input['confirmed'] == False:
                                response.finish()
                                return

                    tool_call_response = await tool_to_call.handle_tool_call(request, response, tool_context, args)

                    function_call_result_message = {
                        "role": "tool",
                        "content": json.dumps(tool_call_response),
                        "tool_call_id": tool_call['id']
                    }

                    messages.append(function_call_result_message)

                if had_tool_call:
                    await _tool_call_loop(tool_call_rounds)
                    return

                if len(tool_call_rounds) > 0:
                    await _tool_call_loop(tool_call_rounds)
                    return
                else:
                    response.finish()
                    return
            except Exception as e:
                log.error(f"Error in tool call loop: {str(e)}")
                response.stream(MarkdownData(f"Oops! I am sorry, there was a problem generating response with tools. Please try again. You can check server logs for more details."))
                response.finish()
                return

        await _tool_call_loop(tool_call_rounds)
    
    def _get_tool_by_name(self, name: str) -> Tool:
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None

class CompletionContextProvider:
    @property
    def id(self) -> str:
        raise NotImplemented

    def handle_completion_context_request(self, request: ContextRequest) -> CompletionContext:
        raise NotImplemented

@dataclass
class LLMProviderProperty:
    id: str
    name: str
    description: str
    value: str
    optional: bool = False

    def to_dict(self):
        return asdict(self)

class LLMPropertyProvider:
    def __init__(self):
        self._properties = []

    @property
    def properties(self) -> list[LLMProviderProperty]:
        return self._properties

    def get_property(self, property_id: str) -> LLMProviderProperty:
        for prop in self.properties:
            if prop.id == property_id:
                return prop
        return None

    def set_property_value(self, property_id: str, value: str):
        for prop in self.properties:
            if prop.id == property_id:
                prop.value = value

class AIModel(LLMPropertyProvider):
    def __init__(self, provider: 'LLMProvider'):
        super().__init__()
        self._provider = provider

    @property
    def id(self) -> str:
        raise NotImplemented
    
    @property
    def name(self) -> str:
        raise NotImplemented

    @property
    def provider(self) -> str:
        return self._provider
    
    @property
    def context_window(self) -> int:
        raise NotImplemented

    @property
    def supports_tools(self) -> bool:
        return False

class ChatModel(AIModel):
    def completions(self, messages: list[dict], tools: list[dict] = None, response: ChatResponse = None, cancel_token: CancelToken = None, options: dict = {}) -> Any:
        raise NotImplemented

class InlineCompletionModel(AIModel):
    def inline_completions(prefix, suffix, language, filename, context: CompletionContext, cancel_token: CancelToken) -> str:
        raise NotImplemented

class EmbeddingModel(AIModel):
    def embeddings(self, inputs: list[str]) -> Any:
        raise NotImplemented

class LLMProvider(LLMPropertyProvider):
    def __init__(self):
        super().__init__()

    @property
    def id(self) -> str:
        raise NotImplemented
    
    @property
    def name(self) -> str:
        raise NotImplemented

    @property
    def chat_models(self) -> list[ChatModel]:
        raise NotImplemented
    
    @property
    def inline_completion_models(self) -> list[InlineCompletionModel]:
        raise NotImplemented
    
    @property
    def embedding_models(self) -> list[EmbeddingModel]:
        raise NotImplemented

    def get_chat_model(self, model_id: str) -> ChatModel:
        for model in self.chat_models:
            if model.id == model_id:
                return model
        return None
    
    def get_inline_completion_model(self, model_id: str) -> InlineCompletionModel:
        for model in self.inline_completion_models:
            if model.id == model_id:
                return model
        return None
    
    def get_embedding_model(self, model_id: str) -> EmbeddingModel:
        for model in self.embedding_models:
            if model.id == model_id:
                return model
        return None

class Host:
    def register_llm_provider(self, provider: LLMProvider) -> None:
        raise NotImplemented

    def register_chat_participant(self, participant: ChatParticipant) -> None:
        raise NotImplemented

    def register_completion_context_provider(self, provider: CompletionContextProvider) -> None:
        raise NotImplemented
    
    @property
    def default_chat_participant(self) -> ChatParticipant:
        raise NotImplemented
    
    @property
    def chat_model(self) -> ChatModel:
        raise NotImplemented
    
    @property
    def inline_completion_model(self) -> InlineCompletionModel:
        raise NotImplemented
    
    @property
    def embedding_model(self) -> EmbeddingModel:
        raise NotImplemented

class NotebookIntelligenceExtension:
    @property
    def id(self) -> str:
        raise NotImplemented

    @property
    def name(self) -> str:
        raise NotImplemented
    
    @property
    def provider(self) -> str:
        raise NotImplemented

    @property
    def url(self) -> str:
        raise NotImplemented

    def activate(self, host: Host) -> None:
        raise NotImplemented
