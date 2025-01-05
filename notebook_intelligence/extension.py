# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import asyncio
import json
from os import path
import os
import sys
from typing import Callable, Dict, Union
from dataclasses import dataclass
from enum import Enum

class RequestDataType(str, Enum):
    ChatRequest = 'chat-request'
    ChatUserInput = 'chat-user-input'
    ClearChatHistory = 'clear-chat-history'
    RunUICommandResponse = 'run-ui-command-response'
    GenerateCode = 'generate-code'

class BackendMessageType(str, Enum):
    StreamMessage = 'stream-message'
    StreamEnd = 'stream-end'
    RunUICommand = 'run-ui-command'

class ResponseStreamDataType(str, Enum):
    LLMRaw = 'llm-raw'
    Markdown = 'markdown'
    MarkdownPart = 'markdown-part'
    HTML = 'html'
    Button = 'button'
    Anchor = 'anchor'
    Progress = 'progress'
    Confirmation = 'confirmation'

    def __str__(self) -> str:
        return self.value

@dataclass
class ChatRequest:
    host: 'Host' = None
    command: str = ''
    prompt: str = ''
    chat_history: list[dict] = None

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
class HTMLData(ResponseStreamData):
    content: str = ''

    @property
    def data_type(self) -> ResponseStreamDataType:
        return ResponseStreamDataType.HTML

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

    @property
    def data_type(self) -> ResponseStreamDataType:
        return ResponseStreamDataType.Confirmation

class ContextType(Enum):
    InlineCompletion = 'inline-completion'
    NewPythonFile = 'new-python-file'
    NewNotebook = 'new-notebook'

@dataclass
class ContextInputFileInfo:
    file_name: str = ''
    parent_dir: str = ''
    server_root: str = ''

@dataclass
class ContextRequest:
    type: ContextType
    prompt: str = ''
    file_info: ContextInputFileInfo = None
    language: str = ''
    prefix: str = ''
    suffix: str = ''
    participant: 'ChatParticipant' = None

@dataclass
class ContextItem:
    content: str
    file_path: str = None

@dataclass
class CompletionContext:
    items: list[ContextItem]

class ChatResponse:
    def __init__(self):
        self._user_input_listeners: list[Callable] = []
        self._run_ui_command_listeners: list[Callable] = []

    @property
    def message_id(self) -> str:
        raise NotImplemented

    def stream(self, data: ResponseStreamData, finish: bool = False) -> None:
        raise NotImplemented
    
    def finish(self) -> None:
        raise NotImplemented
    
    def add_user_input_listener(self, listener: Callable) -> None:
        self._user_input_listeners.append(listener)
    
    def remove_user_input_listener(self, listener: Callable) -> None:
        self._user_input_listeners.remove(listener)

    def on_user_input(self, data: dict) -> None:
        for listener in self._user_input_listeners:
            listener(data)

    @staticmethod
    async def wait_for_chat_user_input(response: 'ChatResponse', callback_id: str):
        resp = {"data": None}
        def _on_user_input(data: dict):
            if data['callback_id'] == callback_id:
                resp["data"] = data['data']

        response.add_user_input_listener(_on_user_input)

        while True:
            if resp["data"] is not None:
                response.remove_user_input_listener(_on_user_input)
                return resp["data"]
            await asyncio.sleep(0.1)

    async def run_ui_command(self, command: str, args: dict = {}) -> None:
        raise NotImplemented
    
    def add_run_ui_command_listener(self, listener: Callable) -> None:
        self._run_ui_command_listeners.append(listener)
    
    def remove_run_ui_command_listener(self, listener: Callable) -> None:
        self._run_ui_command_listeners.remove(listener)

    def on_run_ui_command_response(self, data: dict) -> None:
        for listener in self._run_ui_command_listeners:
            listener(data)

    @staticmethod
    async def wait_for_run_ui_command_response(response: 'ChatResponse', callback_id: str):
        resp = {"result": None}
        def _on_ui_command_response(data: dict):
            if data['callback_id'] == callback_id:
                resp["result"] = data['result']

        response.add_run_ui_command_listener(_on_ui_command_response)

        while True:
            if resp["result"] is not None:
                response.remove_run_ui_command_listener(_on_ui_command_response)
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
            request.host.model.completions(messages, tools=None, response=response)
            return

        openai_tools = [tool.schema for tool in tools]


        tool_call_rounds = []
        options = {'tool_choice': tool_choice}

        async def _tool_call_loop(tool_call_rounds: list):
            tool_response = request.host.model.completions(messages, openai_tools, options=options)
            # after first call, set tool_choice to auto
            options['tool_choice'] = 'auto'

            if 'tool_calls' in tool_response['choices'][0]['message']:
                for tool_call in tool_response['choices'][0]['message']['tool_calls']:
                    tool_call_rounds.append(tool_call)
            elif 'content' in tool_response['choices'][0]['message']:
                messages.append(tool_response['choices'][0]['message'])
                response.stream(MarkdownData(tool_response['choices'][0]['message']['content']))

            # handle first tool call in tool_call_rounds
            if len(tool_call_rounds) > 0:
                tool_call = tool_call_rounds[0]
                tool_call_rounds = tool_call_rounds[1:]

                tool_name = tool_call['function']['name']
                tool_to_call = self._get_tool_by_name(tool_name)
                args = json.loads(tool_call['function']['arguments'])

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

                tool_call_args_resp = args.copy()
                tool_call_args_resp.update(tool_call_response)

                function_call_result_message = {
                    "role": "tool",
                    "content": json.dumps(tool_call_args_resp),
                    "tool_call_id": tool_call['id']
                }

                # TODO: duplicate message?
                messages.append(tool_response['choices'][0]['message'])
                messages.append(function_call_result_message)
                await _tool_call_loop(tool_call_rounds)
                return

            if len(tool_call_rounds) > 0:
                await _tool_call_loop(tool_call_rounds)
                return
            else:
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

class AIModel:
    def completions(self, messages: list[dict], tools: list[dict] = None, response: ChatResponse = None, options: dict = {}) -> None:
        raise NotImplemented

class Host:
    def register_chat_participant(self, participant: ChatParticipant) -> None:
        raise NotImplemented
    
    def register_completion_context_provider(self, provider: CompletionContextProvider) -> None:
        raise NotImplemented
    
    @property
    def model(self) -> AIModel:
        raise NotImplemented

class NotebookIntelligenceExtension:
    @property
    def id(self) -> str:
        raise NotImplemented

    @property
    def name(self) -> str:
        raise NotImplemented

    @property
    def chat_agents(self) -> list[ChatParticipant]:
        raise NotImplemented

    def activate(self, host: Host) -> None:
        raise NotImplemented
