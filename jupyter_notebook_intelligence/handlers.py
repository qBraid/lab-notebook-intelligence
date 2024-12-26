# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import asyncio
import json
from os import path
import os
import sys
import uuid

from jupyter_server.base.handlers import APIHandler
from jupyter_server.utils import url_path_join
import tornado
from tornado import web, websocket
import traitlets
from jupyter_notebook_intelligence.extension import AnchorData, ButtonData, ChatResponse, ChatRequest, ChatParticipant, HTMLData, MarkdownData, NotebookIntelligenceExtension, RequestDataType, ResponseStreamData, ResponseStreamDataType
from jupyter_notebook_intelligence.config import ContextInputFileInfo, ContextRequest, ContextType, NotebookIntelligenceConfig
from jupyter_notebook_intelligence.extension_manager import ExtensionManager
import jupyter_notebook_intelligence.github_copilot as github_copilot
from jupyter_notebook_intelligence.test_extension import TestExtension

extension_manager: ExtensionManager = None

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
        cfg = NotebookIntelligenceConfig(config=self.config)
        data = self.get_json_body()
        prefix = data['prefix']
        suffix = data['suffix']
        language = data['language']
        filename = data['filename']

        context = None
        if cfg.has_context_provider:
            context = cfg.context_provider.get_context(ContextRequest(
                type=ContextType.InlineCompletion,
                file_info=ContextInputFileInfo(
                    file_name=filename       
                ),
                language=language,
                prefix=prefix,
                suffix=suffix
            ))

        completions = github_copilot.inline_completions(prefix, suffix, language, filename, context)
        self.finish(json.dumps({
            "data": completions
        }))

class PostCompletionsHandler(APIHandler):
    @tornado.web.authenticated
    async def post(self):
        data = self.get_json_body()
        messages = data['messages']

        response = github_copilot.completions(messages)
        self.finish(json.dumps(response))

class PostChatHandler(APIHandler):
    @tornado.web.authenticated
    async def post(self):
        cfg = NotebookIntelligenceConfig(config=self.config)
        data = self.get_json_body()
        prompt = data['prompt']
        language = data['language']
        filename = data['filename']

        response = extension_manager.handle_chat_request(ChatRequest(prompt=prompt))
        # data = {"message": response["choices"][0]["message"]["content"]}
    
        self.finish(json.dumps(response))

        # context = None
        # if cfg.has_context_provider:
        #     context = cfg.context_provider.get_context(ContextRequest(
        #         type=ContextType.Chat,
        #         file_info=ContextInputFileInfo(file_name=filename),
        #         language=language,
        #         prefix=prompt
        #     ))

        # response = github_copilot.chat(prompt, language, filename, context)
        # self.finish(json.dumps({
        #     "data": response
        # }))

class WebsocketChatResponseEmitter(ChatResponse):
    def __init__(self, messageId, handler):
        super().__init__()
        self.messageId = messageId
        self.handler = handler

    @property
    def message_id(self) -> str:
        return self.messageId

    # data: OpenAIResponse, MarkdownResponse, etc.
    def stream(self, data: ResponseStreamData | dict):
        data_type = ResponseStreamDataType.LLMRaw if type(data) is dict else data.data_type

        if data_type == ResponseStreamDataType.Markdown:
            data = {
                "choices": [
                    {
                        "delta": {
                            "content": data.content,
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
                                    "confirmButtonTitle": data.confirmButtonTitle,
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

        self.handler.write_message({
            "id": self.messageId,
            "type": "StreamMessage",
            "data": data
        })

    def finish(self) -> None:
        self.handler.write_message({
            "id": self.messageId,
            "type": "StreamEnd",
            "data": {}
        })

class WebsocketChatHandler(websocket.WebSocketHandler):
    def __init__(self, application, request, **kwargs):
        super().__init__(application, request, **kwargs)
        self._responseEmitters = {}

    def open(self):
        print("WebSocket opened")

    def on_message(self, message):
        msg = json.loads(message)

        messageId = msg['id']
        messageType = msg['type']
        if messageType == RequestDataType.ChatRequest:
            data = msg['data']
            prompt = data['prompt']
            language = data['language']
            filename = data['filename']
            responseEmitter = WebsocketChatResponseEmitter(messageId, self)
            self._responseEmitters[messageId] = responseEmitter
            asyncio.create_task(extension_manager.handle_chat_request(ChatRequest(prompt=prompt), responseEmitter))
        elif messageType == RequestDataType.ChatUserInput:
            responseEmitter = self._responseEmitters.get(messageId)
            if responseEmitter is None:
                return
            responseEmitter.on_user_input(msg['data'])
 
    def on_close(self):
        print("WebSocket closed")

class PostExplainThisHandler(APIHandler):
    @tornado.web.authenticated
    async def post(self):
        data = self.get_json_body()
        selection = data['selection']
        language = data['language']
        filename = data['filename']
        response = github_copilot.explain_this(selection, language, filename)
        self.finish(json.dumps(response))

class PostFixThisHandler(APIHandler):
    @tornado.web.authenticated
    async def post(self):
        data = self.get_json_body()
        selection = data['selection']
        language = data['language']
        filename = data['filename']
        response = github_copilot.fix_this(selection, language, filename)
        self.finish(json.dumps(response))

class PostNewNotebookHandler(APIHandler):
    @tornado.web.authenticated
    async def post(self):
        cfg = NotebookIntelligenceConfig(config=self.config)
        data = self.get_json_body()
        prompt = data['prompt']
        parent_path = data['parent-path']

        context = None
        if cfg.has_context_provider:
            context = cfg.context_provider.get_context(ContextRequest(
                type=ContextType.NewNotebook,
                prefix=prompt
            ))

        response = github_copilot.new_notebook(prompt, parent_path, context)
        self.finish(json.dumps(response))

def initialize_extensions():
    global extension_manager
    default_chat_participant = github_copilot.GithubCopilotChatParticipant()
    extension_manager = ExtensionManager(default_chat_participant)
    test_extension = TestExtension()
    test_extension.activate(extension_manager)

def setup_handlers(web_app):
    host_pattern = ".*$"

    base_url = web_app.settings["base_url"]
    route_pattern_github_login_status = url_path_join(base_url, "notebook-intelligence", "gh-login-status")
    route_pattern_github_login = url_path_join(base_url, "notebook-intelligence", "gh-login")
    route_pattern_github_logout = url_path_join(base_url, "notebook-intelligence", "gh-logout")
    route_pattern_inline_completions = url_path_join(base_url, "notebook-intelligence", "inline-completions")
    route_pattern_completions = url_path_join(base_url, "notebook-intelligence", "completions")
    route_pattern_chat = url_path_join(base_url, "notebook-intelligence", "chat")
    route_pattern_explain_this = url_path_join(base_url, "notebook-intelligence", "explain-this")
    route_pattern_fix_this = url_path_join(base_url, "notebook-intelligence", "fix-this")
    route_pattern_new_notebook = url_path_join(base_url, "notebook-intelligence", "new-notebook")
    handlers = [
        (route_pattern_github_login_status, GetGitHubLoginStatusHandler),
        (route_pattern_github_login, PostGitHubLoginHandler),
        (route_pattern_github_logout, GetGitHubLogoutHandler),
        (route_pattern_inline_completions, PostInlineCompletionsHandler),
        (route_pattern_completions, PostCompletionsHandler),
        # (route_pattern_chat, PostChatHandler),
        (route_pattern_chat, WebsocketChatHandler),
        (route_pattern_explain_this, PostExplainThisHandler),
        (route_pattern_fix_this, PostFixThisHandler),
        (route_pattern_new_notebook, PostNewNotebookHandler),
    ]
    web_app.add_handlers(host_pattern, handlers)
