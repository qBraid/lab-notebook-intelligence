# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import asyncio
import json
from os import path
import os
import sys
from typing import Union
import uuid

from jupyter_server.extension.application import ExtensionApp
from jupyter_server.base.handlers import APIHandler
from jupyter_server.utils import url_path_join
import tornado
from tornado import web, websocket
from notebook_intelligence.extension import ChatResponse, ChatRequest, ContextRequest, ContextType, RequestDataType, ResponseStreamData, ResponseStreamDataType, BackendMessageType
from notebook_intelligence.extension_manager import ExtensionManager
import notebook_intelligence.github_copilot as github_copilot

extension_manager: ExtensionManager = None

class GetCapabilitiesHandler(APIHandler):
    @tornado.web.authenticated
    def get(self):
        response = {
            "chat_participants": []
        }
        for participant_id in extension_manager.chat_participants:
            participant = extension_manager.chat_participants[participant_id]
            response["chat_participants"].append({
                "id": participant.id,
                "commands": [command.name for command in participant.commands]
            })
        self.finish(json.dumps(response))

class GetGitHubLoginStatusHandler(APIHandler):
    # The following decorator should be present on all verb methods (head, get, post,
    # patch, put, delete, options) to ensure only authorized user can request the
    # Jupyter server
    @tornado.web.authenticated
    def get(self):
        self.finish(json.dumps(github_copilot.get_login_status()))

class PostGitHubLoginHandler(APIHandler):
    @tornado.web.authenticated
    def post(self):
        self.finish(json.dumps(github_copilot.login()))

class GetGitHubLogoutHandler(APIHandler):
    @tornado.web.authenticated
    def get(self):
        self.finish(json.dumps(github_copilot.logout()))


class PostInlineCompletionsHandler(APIHandler):
    @tornado.web.authenticated
    async def post(self):
        data = self.get_json_body()
        prefix = data['prefix']
        suffix = data['suffix']
        language = data['language']
        filename = data['filename']

        context = await extension_manager.get_completion_context(ContextRequest(ContextType.InlineCompletion, prefix, suffix, language, filename, participant=extension_manager.get_chat_participant(prefix)))
        completions = github_copilot.inline_completions(prefix, suffix, language, filename, context)
        self.finish(json.dumps({
            "data": completions
        }))

class ChatHistory:
    """
    History of chat messages, key is chat id, value is list of messages
    keep the last 10 messages in the same chat participant
    """
    MAX_MESSAGES = 10

    def __init__(self):
        self.messages = {}

    def clear(self, chatId = None):
        if chatId is None:
            self.messages = {}
            return True
        elif chatId in self.messages:
            del self.messages[chatId]
            return True

        return False

    def add_message(self, chatId, message):
        if chatId not in self.messages:
            self.messages[chatId] = []

        # clear the chat history if participant changed
        if message["role"] == "user":
            existing_messages = self.messages[chatId]
            prev_user_message = next((m for m in reversed(existing_messages) if m["role"] == "user"), None)
            if prev_user_message is not None:
                (current_participant, command, prompt) = ExtensionManager.parse_prompt(message["content"])
                (prev_participant, command, prompt) = ExtensionManager.parse_prompt(prev_user_message["content"])
                if current_participant != prev_participant:
                    self.messages[chatId] = []

        self.messages[chatId].append(message)
        # limit number of messages kept in history
        if len(self.messages[chatId]) > ChatHistory.MAX_MESSAGES:
            self.messages[chatId] = self.messages[chatId][-ChatHistory.MAX_MESSAGES:]

    def get_history(self, chatId):
        return self.messages.get(chatId, [])

class WebsocketChatResponseEmitter(ChatResponse):
    def __init__(self, chatId, messageId, websocket_handler, chat_history):
        super().__init__()
        self.chatId = chatId
        self.messageId = messageId
        self.websocket_handler = websocket_handler
        self.chat_history = chat_history
        self.streamed_contents = []

    @property
    def chat_id(self) -> str:
        return self.chatId

    @property
    def message_id(self) -> str:
        return self.messageId

    def stream(self, data: Union[ResponseStreamData, dict]):
        data_type = ResponseStreamDataType.LLMRaw if type(data) is dict else data.data_type

        if data_type == ResponseStreamDataType.Markdown:
            self.chat_history.add_message(self.chatId, {"role": "assistant", "content": data.content})
            data = {
                "choices": [
                    {
                        "delta": {
                            "nbiContent": {
                                "type": data_type,
                                "content": data.content
                            },
                            "content": "",
                            "role": "assistant"
                        }
                    }
                ]
            }
        elif data_type == ResponseStreamDataType.HTML:
            data = {
                "choices": [
                    {
                        "delta": {
                            "nbiContent": {
                                "type": data_type,
                                "content": data.content
                            },
                            "content": "",
                            "role": "assistant"
                        }
                    }
                ]
            }
        elif data_type == ResponseStreamDataType.Anchor:
            data = {
                "choices": [
                    {
                        "delta": {
                            "nbiContent": {
                                "type": data_type,
                                "content": {
                                    "uri": data.uri,
                                    "title": data.title
                                }
                            },
                            "content": "",
                            "role": "assistant"
                        }
                    }
                ]
            }
        elif data_type == ResponseStreamDataType.Button:
            data = {
                "choices": [
                    {
                        "delta": {
                            "nbiContent": {
                                "type": data_type,
                                "content": {
                                    "title": data.title,
                                    "commandId": data.commandId,
                                    "args": data.args if data.args is not None else {}
                                }
                            },
                            "content": "",
                            "role": "assistant"
                        }
                    }
                ]
            }
        elif data_type == ResponseStreamDataType.Progress:
            data = {
                "choices": [
                    {
                        "delta": {
                            "nbiContent": {
                                "type": data_type,
                                "content": data.title
                            },
                            "content": "",
                            "role": "assistant"
                        }
                    }
                ]
            }
        elif data_type == ResponseStreamDataType.Confirmation:
            data = {
                "choices": [
                    {
                        "delta": {
                            "nbiContent": {
                                "type": data_type,
                                "content": {
                                    "title": data.title,
                                    "message": data.message,
                                    "confirmArgs": data.confirmArgs if data.confirmArgs is not None else {},
                                    "cancelArgs": data.cancelArgs if data.cancelArgs is not None else {}
                                }
                            },
                            "content": "",
                            "role": "assistant"
                        }
                    }
                ]
            }
        else: # ResponseStreamDataType.LLMRaw
            if len(data.get("choices", [])) > 0:
                part = data["choices"][0].get("delta", {}).get("content", "")
                if part is not None:
                    self.streamed_contents.append(part)

        self.websocket_handler.write_message({
            "id": self.messageId,
            "type": BackendMessageType.StreamMessage,
            "data": data
        })

    def finish(self) -> None:
        self.chat_history.add_message(self.chatId, {"role": "assistant", "content": "".join(self.streamed_contents)})
        self.streamed_contents = []
        self.websocket_handler.write_message({
            "id": self.messageId,
            "type": BackendMessageType.StreamEnd,
            "data": {}
        })

    async def run_ui_command(self, command: str, args: dict = {}) -> None:
        callback_id = str(uuid.uuid4())
        self.websocket_handler.write_message({
            "id": self.messageId,
            "type": BackendMessageType.RunUICommand,
            "data": {
                "callback_id": callback_id,
                "commandId": command,
                "args": args
            }
        })
        response = await ChatResponse.wait_for_run_ui_command_response(self, callback_id)
        return response

class WebsocketChatHandler(websocket.WebSocketHandler):
    def __init__(self, application, request, **kwargs):
        super().__init__(application, request, **kwargs)
        self._responseEmitters = {}
        self.chat_history = ChatHistory()

    def open(self):
        pass

    def on_message(self, message):
        msg = json.loads(message)

        messageId = msg['id']
        messageType = msg['type']
        if messageType == RequestDataType.ChatRequest:
            data = msg['data']
            chatId = data['chatId']
            prompt = data['prompt']
            language = data['language']
            filename = data['filename']
            self.chat_history.add_message(chatId, {"role": "user", "content": prompt})
            responseEmitter = WebsocketChatResponseEmitter(chatId, messageId, self, self.chat_history)
            self._responseEmitters[messageId] = responseEmitter
            asyncio.create_task(extension_manager.handle_chat_request(ChatRequest(prompt=prompt, chat_history=self.chat_history.get_history(chatId)), responseEmitter))
        elif messageType == RequestDataType.GenerateCode:
            data = msg['data']
            chatId = data['chatId']
            prompt = data['prompt']
            prefix = data['prefix']
            suffix = data['suffix']
            existing_code = data['existingCode']
            language = data['language']
            filename = data['filename']
            if prefix != '':
                self.chat_history.add_message(chatId, {"role": "user", "content": f"This prefix code section comes before the code section you will generate: ```{prefix}```"})
            if suffix != '':
                self.chat_history.add_message(chatId, {"role": "user", "content": f"This suffix code section comes after the code section  you will generate: ```{suffix}```"})
            if existing_code != '':
                self.chat_history.add_message(chatId, {"role": "user", "content": f"You are asked to generate updates for or a replacement for the existing code. This is the existing code. : ```{existing_code}```"})
            self.chat_history.add_message(chatId, {"role": "user", "content": f"Generate code for: {prompt}"})
            responseEmitter = WebsocketChatResponseEmitter(chatId, messageId, self, self.chat_history)
            self._responseEmitters[messageId] = responseEmitter
            asyncio.create_task(extension_manager.handle_chat_request(ChatRequest(prompt=prompt, chat_history=self.chat_history.get_history(chatId)), responseEmitter, options={"system_prompt": f"You are an assistant that generates code for '{language}' language. You generate code between existing prefix and suffix code sections. You update or replace an existing code section. Prefix, suffix and existing code are all optional. If the request is relevant to the existing code, assume an update is requested. If updates to existing code are requested, update it with the requested changes. If updates are requested, update the existing code and return the existing code section with the updates applied, do not just return the update as your response will be replacing the existing code. Be concise and return only code as a response."}))
        elif messageType == RequestDataType.ChatUserInput:
            responseEmitter = self._responseEmitters.get(messageId)
            if responseEmitter is None:
                return
            responseEmitter.on_user_input(msg['data'])
        elif messageType == RequestDataType.ClearChatHistory:
            self.chat_history.clear(msg['data']['chatId'])
        elif messageType == RequestDataType.RunUICommandResponse:
            responseEmitter = self._responseEmitters.get(messageId)
            if responseEmitter is None:
                return
            responseEmitter.on_run_ui_command_response(msg['data'])
 
    def on_close(self):
        pass

def initialize_extensions():
    global extension_manager
    default_chat_participant = github_copilot.GithubCopilotChatParticipant()
    extension_manager = ExtensionManager(default_chat_participant)


class NotebookIntelligenceJupyterExtApp(ExtensionApp):
    name = "notebook_intelligence"
    default_url = "/notebook-intelligence"
    load_other_extensions = True
    file_url_prefix = "/render"

    static_paths = []
    template_paths = []
    settings = {}
    handlers = []

    def initialize_settings(self):
        pass

    def initialize_handlers(self):
        initialize_extensions()
        self._setup_handlers(self.serverapp.web_app)
        self.serverapp.log.info(f"Registered {self.name} server extension")

    def initialize_templates(self):
        pass

    async def stop_extension(self):
        print(f"Stopping {self.name} extension...")
        github_copilot.handle_stop_request()

    def _setup_handlers(self, web_app):
        host_pattern = ".*$"

        base_url = web_app.settings["base_url"]
        route_pattern_capabilities = url_path_join(base_url, "notebook-intelligence", "capabilities")
        route_pattern_github_login_status = url_path_join(base_url, "notebook-intelligence", "gh-login-status")
        route_pattern_github_login = url_path_join(base_url, "notebook-intelligence", "gh-login")
        route_pattern_github_logout = url_path_join(base_url, "notebook-intelligence", "gh-logout")
        route_pattern_inline_completions = url_path_join(base_url, "notebook-intelligence", "inline-completions")
        route_pattern_chat = url_path_join(base_url, "notebook-intelligence", "chat")
        NotebookIntelligenceJupyterExtApp.handlers = [
            (route_pattern_capabilities, GetCapabilitiesHandler),
            (route_pattern_github_login_status, GetGitHubLoginStatusHandler),
            (route_pattern_github_login, PostGitHubLoginHandler),
            (route_pattern_github_logout, GetGitHubLogoutHandler),
            (route_pattern_inline_completions, PostInlineCompletionsHandler),
            (route_pattern_chat, WebsocketChatHandler),
        ]
        web_app.add_handlers(host_pattern, NotebookIntelligenceJupyterExtApp.handlers)
