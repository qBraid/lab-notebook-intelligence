# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import asyncio
import datetime as dt
import json
import logging
import os
import threading
import uuid
from dataclasses import dataclass
from os import path
from typing import Union

import tiktoken
import tornado
from jupyter_server.base.handlers import APIHandler
from jupyter_server.extension.application import ExtensionApp
from jupyter_server.utils import url_path_join
from tornado import websocket
from traitlets import Unicode

import lab_notebook_intelligence.github_copilot as github_copilot
from lab_notebook_intelligence.ai_service_manager import AIServiceManager
from lab_notebook_intelligence.api import (
    BackendMessageType,
    BuiltinToolset,
    CancelToken,
    ChatMode,
    ChatRequest,
    ChatResponse,
    ContextRequest,
    ContextRequestType,
    RequestDataType,
    RequestToolSelection,
    ResponseStreamData,
    ResponseStreamDataType,
    SignalImpl,
)
from lab_notebook_intelligence.built_in_toolsets import built_in_toolsets
from lab_notebook_intelligence.util import ThreadSafeWebSocketConnector

ai_service_manager: AIServiceManager = None
log = logging.getLogger(__name__)
tiktoken_encoding = tiktoken.encoding_for_model("gpt-4o")


class GetCapabilitiesHandler(APIHandler):
    notebook_execute_tool = "enabled"

    @tornado.web.authenticated
    def get(self):
        ai_service_manager.update_models_from_config()
        nbi_config = ai_service_manager.nbi_config
        llm_providers = ai_service_manager.llm_providers.values()
        notebook_execute_tool_enabled = self.notebook_execute_tool == "enabled" or (
            self.notebook_execute_tool == "env_enabled"
            and os.getenv("NBI_NOTEBOOK_EXECUTE_TOOL", "disabled") == "enabled"
        )
        allowed_builtin_toolsets = [
            {"id": toolset.id, "name": toolset.name}
            for toolset in built_in_toolsets.values()
            if toolset.id != BuiltinToolset.NotebookExecute
            or notebook_execute_tool_enabled
        ]
        mcp_servers = ai_service_manager.get_mcp_servers()
        mcp_server_tools = [
            {
                "id": mcp_server.name,
                "tools": [
                    {"name": tool.name, "description": tool.description}
                    for tool in mcp_server.get_tools()
                ],
            }
            for mcp_server in mcp_servers
        ]
        mcp_server_tools = [tool for tool in mcp_server_tools if len(tool["tools"]) > 0]
        # sort by server id
        mcp_server_tools.sort(key=lambda server: server["id"])

        extensions = []
        for (
            extension_id,
            toolsets,
        ) in ai_service_manager.get_extension_toolsets().items():
            ts = []
            for toolset in toolsets:
                tools = []
                for tool in toolset.tools:
                    tools.append({"name": tool.name, "description": tool.description})
                # sort by tool name
                tools.sort(key=lambda tool: tool["name"])
                ts.append(
                    {
                        "id": toolset.id,
                        "name": toolset.name,
                        "description": toolset.description,
                        "tools": tools,
                    }
                )
            # sort by toolset name
            ts.sort(key=lambda toolset: toolset["name"])
            extension = ai_service_manager.get_extension(extension_id)
            extensions.append(
                {"id": extension_id, "name": extension.name, "toolsets": ts}
            )
        # sort by extension id
        extensions.sort(key=lambda extension: extension["id"])

        response = {
            "user_home_dir": os.path.expanduser("~"),
            "nbi_user_config_dir": nbi_config.nbi_user_dir,
            "using_github_copilot_service": nbi_config.using_github_copilot_service,
            "llm_providers": [
                {"id": provider.id, "name": provider.name} for provider in llm_providers
            ],
            "chat_models": ai_service_manager.chat_model_ids,
            "inline_completion_models": ai_service_manager.inline_completion_model_ids,
            "embedding_models": ai_service_manager.embedding_model_ids,
            "chat_model": nbi_config.chat_model,
            "inline_completion_model": nbi_config.inline_completion_model,
            "embedding_model": nbi_config.embedding_model,
            "chat_participants": [],
            "store_github_access_token": nbi_config.store_github_access_token,
            "tool_config": {
                "builtinToolsets": allowed_builtin_toolsets,
                "mcpServers": mcp_server_tools,
                "extensions": extensions,
            },
            "default_chat_mode": nbi_config.default_chat_mode,
        }
        for participant_id in ai_service_manager.chat_participants:
            participant = ai_service_manager.chat_participants[participant_id]
            response["chat_participants"].append(
                {
                    "id": participant.id,
                    "name": participant.name,
                    "description": participant.description,
                    "iconPath": participant.icon_path,
                    "commands": [command.name for command in participant.commands],
                }
            )
        self.finish(json.dumps(response))


class ConfigHandler(APIHandler):
    @tornado.web.authenticated
    def post(self):
        data = json.loads(self.request.body)
        valid_keys = set(
            [
                "default_chat_mode",
                "chat_model",
                "inline_completion_model",
                "store_github_access_token",
            ]
        )
        for key in data:
            if key in valid_keys:
                ai_service_manager.nbi_config.set(key, data[key])
                if key == "store_github_access_token":
                    if data[key]:
                        github_copilot.store_github_access_token()
                    else:
                        github_copilot.delete_stored_github_access_token()
        ai_service_manager.nbi_config.save()
        ai_service_manager.update_models_from_config()
        self.finish(json.dumps({}))


class UpdateProviderModelsHandler(APIHandler):
    @tornado.web.authenticated
    def post(self):
        data = json.loads(self.request.body)
        if data.get("provider") == "ollama":
            ai_service_manager.ollama_llm_provider.update_chat_model_list()
        self.finish(json.dumps({}))


class ReloadMCPServersHandler(APIHandler):
    @tornado.web.authenticated
    def post(self):
        ai_service_manager.nbi_config.load()
        ai_service_manager.update_mcp_servers()
        self.finish(
            json.dumps(
                {
                    "mcpServers": [
                        {"id": server.name}
                        for server in ai_service_manager.get_mcp_servers()
                    ]
                }
            )
        )


class MCPConfigFileHandler(APIHandler):
    @tornado.web.authenticated
    def get(self):
        mcp_config = ai_service_manager.nbi_config.mcp.copy()
        if "mcpServers" not in mcp_config:
            mcp_config["mcpServers"] = {}
        self.finish(json.dumps(mcp_config))

    @tornado.web.authenticated
    def post(self):
        try:
            data = json.loads(self.request.body)
            ai_service_manager.nbi_config.user_mcp = data
            ai_service_manager.nbi_config.save()
            ai_service_manager.nbi_config.load()
            ai_service_manager.update_mcp_servers()
            self.finish(json.dumps({"status": "ok"}))
        except Exception as e:
            self.finish(json.dumps({"status": "error", "message": str(e)}))
            return


class CreateDynamicMCPConfigHandler(APIHandler):
    @tornado.web.authenticated
    def post(self):
        try:
            # Get the directory where JupyterLab was started (user's working directory)
            user_root_dir = NotebookIntelligence.root_dir

            print(f"Creating dynamic MCP config for directory: {user_root_dir}")

            # Create dynamic MCP config with filesystem servers
            dynamic_mcp_config = {
                "mcpServers": {
                    "filesystem-pwd": {
                        "command": "npx",
                        "args": [
                            "-y",
                            "@modelcontextprotocol/server-filesystem",
                            user_root_dir,
                        ],
                    },
                    "qbraid-web-search": {
                        "command": "uv",
                        "args": ["tool", "run", "web-browser-mcp-server"],
                        "env": {
                            "REQUEST_TIMEOUT": "60",
                        },
                    },
                    # add the MCP server for accessing docs.qbraid.com
                    "qbraid-docs-search": {"url": "https://docs.qbraid.com/mcp"},
                }
            }

            # Add qBraid environments MCP server
            qbraid_envs_dir = os.path.expanduser("~/.qbraid/environments/")
            print(f"qBraid environments directory: {qbraid_envs_dir}")
            if os.path.exists(qbraid_envs_dir):
                # Add filesystem access to environments directory
                dynamic_mcp_config["mcpServers"]["qbraid-envs"] = {
                    "command": "npx",
                    "args": [
                        "-y",
                        "@modelcontextprotocol/server-filesystem",
                        qbraid_envs_dir,
                    ],
                }
                print(f"Added qBraid environments MCP server")

                # TODO: Uncomment and fix the code below to add individual Python execution servers for each qBraid environment

                # # Discover individual environments and add Python execution servers
                # try:
                #     env_count = 0
                #     for env_name in os.listdir(qbraid_envs_dir):
                #         env_path = os.path.join(qbraid_envs_dir, env_name)
                #         python_executable = os.path.join(env_path, "bin", "python")

                #         # Check if this is a valid environment with Python
                #         if (os.path.isdir(env_path) and
                #             os.path.exists(python_executable) and
                #             not env_name.startswith('.')):

                #             # Add Python execution server for this environment
                #             server_name = f"python-{env_name}"
                #             dynamic_mcp_config["mcpServers"][server_name] = {
                #                 "command": "npx",
                #                 "args": [
                #                     "-y",
                #                     "@modelcontextprotocol/python-mcp"
                #                 ],
                #                 "env": {
                #                     "PYTHON_EXECUTABLE": python_executable
                #                 }
                #             }
                #             env_count += 1
                #             print(f"Added Python execution server for environment: {env_name}")

                #     print(f"Discovered and added {env_count} qBraid environment Python servers")
                # except Exception as e:
                #     print(f"Error discovering qBraid environments: {e}")

            else:
                print(f"qBraid environments directory not found: {qbraid_envs_dir}")

            # Save to user's MCP config (this will merge with existing config)
            ai_service_manager.nbi_config.user_mcp = dynamic_mcp_config
            ai_service_manager.nbi_config.save()
            ai_service_manager.nbi_config.load()
            ai_service_manager.update_mcp_servers()

            self.finish(
                json.dumps(
                    {
                        "status": "ok",
                        "message": f"Dynamic MCP config created for directory: {user_root_dir}",
                    }
                )
            )
        except Exception as e:
            self.finish(json.dumps({"status": "error", "message": str(e)}))
            return


class EmitTelemetryEventHandler(APIHandler):
    @tornado.web.authenticated
    def post(self):
        event = json.loads(self.request.body)
        thread = threading.Thread(
            target=asyncio.run, args=(ai_service_manager.emit_telemetry_event(event),)
        )
        thread.start()
        self.finish(json.dumps({}))


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
        device_verification_info = github_copilot.login()
        if device_verification_info is None:
            self.set_status(500)
            self.finish(
                json.dumps(
                    {
                        "error": "Failed to get device verification info from GitHub Copilot"
                    }
                )
            )
            return
        self.finish(json.dumps(device_verification_info))


class GetGitHubLogoutHandler(APIHandler):
    @tornado.web.authenticated
    def get(self):
        self.finish(json.dumps(github_copilot.logout()))


class ChatHistory:
    """
    History of chat messages, key is chat id, value is list of messages
    keep the last 10 messages in the same chat participant
    """

    MAX_MESSAGES = 10

    def __init__(self):
        self.messages = {}

    def clear(self, chatId=None):
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
            prev_user_message = next(
                (m for m in reversed(existing_messages) if m["role"] == "user"), None
            )
            if prev_user_message is not None:
                (current_participant, command, prompt) = AIServiceManager.parse_prompt(
                    message["content"]
                )
                (prev_participant, command, prompt) = AIServiceManager.parse_prompt(
                    prev_user_message["content"]
                )
                if current_participant != prev_participant:
                    self.messages[chatId] = []

        self.messages[chatId].append(message)
        # limit number of messages kept in history
        if len(self.messages[chatId]) > ChatHistory.MAX_MESSAGES:
            self.messages[chatId] = self.messages[chatId][-ChatHistory.MAX_MESSAGES :]

    def get_history(self, chatId):
        return self.messages.get(chatId, [])


class WebsocketCopilotResponseEmitter(ChatResponse):
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
        data_type = (
            ResponseStreamDataType.LLMRaw if type(data) is dict else data.data_type
        )

        if data_type == ResponseStreamDataType.Markdown:
            self.chat_history.add_message(
                self.chatId, {"role": "assistant", "content": data.content}
            )
            data = {
                "choices": [
                    {
                        "delta": {
                            "nbiContent": {
                                "type": data_type,
                                "content": data.content,
                                "detail": data.detail,
                            },
                            "content": "",
                            "role": "assistant",
                        }
                    }
                ]
            }
        elif data_type == ResponseStreamDataType.Image:
            data = {
                "choices": [
                    {
                        "delta": {
                            "nbiContent": {"type": data_type, "content": data.content},
                            "content": "",
                            "role": "assistant",
                        }
                    }
                ]
            }
        elif data_type == ResponseStreamDataType.HTMLFrame:
            data = {
                "choices": [
                    {
                        "delta": {
                            "nbiContent": {
                                "type": data_type,
                                "content": {
                                    "source": data.source,
                                    "height": data.height,
                                },
                            },
                            "content": "",
                            "role": "assistant",
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
                                "content": {"uri": data.uri, "title": data.title},
                            },
                            "content": "",
                            "role": "assistant",
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
                                    "args": data.args if data.args is not None else {},
                                },
                            },
                            "content": "",
                            "role": "assistant",
                        }
                    }
                ]
            }
        elif data_type == ResponseStreamDataType.Progress:
            data = {
                "choices": [
                    {
                        "delta": {
                            "nbiContent": {"type": data_type, "content": data.title},
                            "content": "",
                            "role": "assistant",
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
                                    "confirmArgs": (
                                        data.confirmArgs
                                        if data.confirmArgs is not None
                                        else {}
                                    ),
                                    "cancelArgs": (
                                        data.cancelArgs
                                        if data.cancelArgs is not None
                                        else {}
                                    ),
                                    "confirmLabel": (
                                        data.confirmLabel
                                        if data.confirmLabel is not None
                                        else "Approve"
                                    ),
                                    "cancelLabel": (
                                        data.cancelLabel
                                        if data.cancelLabel is not None
                                        else "Cancel"
                                    ),
                                },
                            },
                            "content": "",
                            "role": "assistant",
                        }
                    }
                ]
            }
        elif data_type == ResponseStreamDataType.MarkdownPart:
            content = data.content
            data = {
                "choices": [
                    {
                        "delta": {
                            "nbiContent": {"type": data_type, "content": data.content},
                            "content": "",
                            "role": "assistant",
                        }
                    }
                ]
            }
            part = content
            if part is not None:
                self.streamed_contents.append(part)
        else:  # ResponseStreamDataType.LLMRaw
            if len(data.get("choices", [])) > 0:
                part = data["choices"][0].get("delta", {}).get("content", "")
                if part is not None:
                    self.streamed_contents.append(part)

        self.websocket_handler.write_message(
            {
                "id": self.messageId,
                "participant": self.participant_id,
                "type": BackendMessageType.StreamMessage,
                "data": data,
                "created": dt.datetime.now().isoformat(),
            }
        )

    def finish(self) -> None:
        self.chat_history.add_message(
            self.chatId,
            {"role": "assistant", "content": "".join(self.streamed_contents)},
        )
        self.streamed_contents = []
        self.websocket_handler.write_message(
            {
                "id": self.messageId,
                "participant": self.participant_id,
                "type": BackendMessageType.StreamEnd,
                "data": {},
            }
        )

    async def run_ui_command(self, command: str, args: dict = {}) -> None:
        callback_id = str(uuid.uuid4())
        self.websocket_handler.write_message(
            {
                "id": self.messageId,
                "participant": self.participant_id,
                "type": BackendMessageType.RunUICommand,
                "data": {
                    "callback_id": callback_id,
                    "commandId": command,
                    "args": args,
                },
            }
        )
        response = await ChatResponse.wait_for_run_ui_command_response(
            self, callback_id
        )
        return response


class CancelTokenImpl(CancelToken):
    def __init__(self):
        super().__init__()
        self._cancellation_signal = SignalImpl()

    def cancel_request(self) -> None:
        self._cancellation_requested = True
        self._cancellation_signal.emit()


@dataclass
class MessageCallbackHandlers:
    response_emitter: WebsocketCopilotResponseEmitter
    cancel_token: CancelTokenImpl


class WebsocketCopilotHandler(websocket.WebSocketHandler):
    def __init__(self, application, request, **kwargs):
        super().__init__(application, request, **kwargs)
        # TODO: cleanup
        self._messageCallbackHandlers: dict[str, MessageCallbackHandlers] = {}
        self.chat_history = ChatHistory()
        github_copilot.websocket_connector = ThreadSafeWebSocketConnector(self)

    def open(self):
        pass

    def on_message(self, message):
        msg = json.loads(message)

        messageId = msg["id"]
        messageType = msg["type"]
        if messageType == RequestDataType.ChatRequest:
            data = msg["data"]
            chatId = data["chatId"]
            prompt = data["prompt"]
            language = data["language"]
            filename = data["filename"]
            additionalContext = data.get("additionalContext", [])
            chat_mode = (
                ChatMode("agent", "Agent")
                if data.get("chatMode", "ask") == "agent"
                else ChatMode("ask", "Ask")
            )
            toolSelections = data.get("toolSelections", {})
            tool_selection = RequestToolSelection(
                built_in_toolsets=toolSelections.get("builtinToolsets", []),
                mcp_server_tools=toolSelections.get("mcpServers", {}),
                extension_tools=toolSelections.get("extensions", {}),
            )

            request_chat_history = self.chat_history.get_history(chatId).copy()

            token_limit = (
                100
                if ai_service_manager.chat_model is None
                else ai_service_manager.chat_model.context_window
            )
            token_budget = 0.8 * token_limit

            for context in additionalContext:
                file_path = context["filePath"]

                file_path = path.join(NotebookIntelligence.root_dir, file_path)
                filename = path.basename(file_path)
                start_line = context.get("startLine", 0)
                end_line = context.get("endLine", 0)
                current_cell_contents = context.get("currentCellContents", {})
                current_cell_input = current_cell_contents.get("input", "")
                current_cell_output = current_cell_contents.get("output", "")

                current_cell_context = (
                    f"This is a Jupyter notebook and currently selected cell input is: ```{current_cell_input}``` and currently selected cell output is: ```{current_cell_output}```. If user asks a question about 'this' cell then assume that user is referring to currently selected cell."
                    if current_cell_contents is not None
                    else ""
                )
                context_content = context.get("content", "")
                token_count = len(tiktoken_encoding.encode(context_content))
                if token_count > token_budget:
                    context_content = context_content[: int(token_budget)] + "..."
                msg_content = f"Use this as additional context: ```{context_content}```. It is from current file: '{filename}' at path '{file_path}'"
                if start_line >= 0 and end_line > 0:
                    msg_content += f", lines: {start_line} - {end_line}."
                if current_cell_context != "":
                    msg_content += f" {current_cell_context}"

                request_chat_history.append(
                    {
                        "role": "user",
                        "content": msg_content,
                    }
                )
                self.chat_history.add_message(
                    chatId,
                    {
                        "role": "user",
                        "content": f"This file was provided as additional context: '{filename}' at path '{file_path}'. {current_cell_context}",
                    },
                )

            self.chat_history.add_message(chatId, {"role": "user", "content": prompt})
            request_chat_history.append({"role": "user", "content": prompt})
            response_emitter = WebsocketCopilotResponseEmitter(
                chatId, messageId, self, self.chat_history
            )
            cancel_token = CancelTokenImpl()
            self._messageCallbackHandlers[messageId] = MessageCallbackHandlers(
                response_emitter, cancel_token
            )
            thread = threading.Thread(
                target=asyncio.run,
                args=(
                    ai_service_manager.handle_chat_request(
                        ChatRequest(
                            chat_mode=chat_mode,
                            tool_selection=tool_selection,
                            prompt=prompt,
                            chat_history=request_chat_history,
                            cancel_token=cancel_token,
                        ),
                        response_emitter,
                    ),
                ),
            )
            thread.start()
        elif messageType == RequestDataType.GenerateCode:
            data = msg["data"]
            chatId = data["chatId"]
            prompt = data["prompt"]
            prefix = data["prefix"]
            suffix = data["suffix"]
            existing_code = data["existingCode"]
            language = data["language"]
            filename = data["filename"]
            chat_mode = ChatMode("ask", "Ask")
            if prefix != "":
                self.chat_history.add_message(
                    chatId,
                    {
                        "role": "user",
                        "content": f"This code section comes before the code section you will generate, use as context. Leading content: ```{prefix}```",
                    },
                )
            if suffix != "":
                self.chat_history.add_message(
                    chatId,
                    {
                        "role": "user",
                        "content": f"This code section comes after the code section you will generate, use as context. Trailing content: ```{suffix}```",
                    },
                )
            if existing_code != "":
                self.chat_history.add_message(
                    chatId,
                    {
                        "role": "user",
                        "content": f"You are asked to modify the existing code. Generate a replacement for this existing code : ```{existing_code}```",
                    },
                )
            self.chat_history.add_message(
                chatId, {"role": "user", "content": f"Generate code for: {prompt}"}
            )
            response_emitter = WebsocketCopilotResponseEmitter(
                chatId, messageId, self, self.chat_history
            )
            cancel_token = CancelTokenImpl()
            self._messageCallbackHandlers[messageId] = MessageCallbackHandlers(
                response_emitter, cancel_token
            )
            existing_code_message = (
                " Update the existing code section and return a modified version. Don't just return the update, recreate the existing code section with the update."
                if existing_code != ""
                else ""
            )
            thread = threading.Thread(
                target=asyncio.run,
                args=(
                    ai_service_manager.handle_chat_request(
                        ChatRequest(
                            chat_mode=chat_mode,
                            prompt=prompt,
                            chat_history=self.chat_history.get_history(chatId),
                            cancel_token=cancel_token,
                        ),
                        response_emitter,
                        options={
                            "system_prompt": f"You are an assistant that generates code for '{language}' language. You generate code between existing leading and trailing code sections.{existing_code_message} Be concise and return only code as a response. Don't include leading content or trailing content in your response, they are provided only for context. You can reuse methods and symbols defined in leading and trailing content."
                        },
                    ),
                ),
            )
            thread.start()
        elif messageType == RequestDataType.InlineCompletionRequest:
            data = msg["data"]
            chatId = data["chatId"]
            prefix = data["prefix"]
            suffix = data["suffix"]
            language = data["language"]
            filename = data["filename"]
            chat_history = ChatHistory()

            response_emitter = WebsocketCopilotResponseEmitter(
                chatId, messageId, self, chat_history
            )
            cancel_token = CancelTokenImpl()
            self._messageCallbackHandlers[messageId] = MessageCallbackHandlers(
                response_emitter, cancel_token
            )

            thread = threading.Thread(
                target=asyncio.run,
                args=(
                    WebsocketCopilotHandler.handle_inline_completions(
                        prefix,
                        suffix,
                        language,
                        filename,
                        response_emitter,
                        cancel_token,
                    ),
                ),
            )
            thread.start()
        elif messageType == RequestDataType.ChatUserInput:
            handlers = self._messageCallbackHandlers.get(messageId)
            if handlers is None:
                return
            handlers.response_emitter.on_user_input(msg["data"])
        elif messageType == RequestDataType.ClearChatHistory:
            self.chat_history.clear()
        elif messageType == RequestDataType.RunUICommandResponse:
            handlers = self._messageCallbackHandlers.get(messageId)
            if handlers is None:
                return
            handlers.response_emitter.on_run_ui_command_response(msg["data"])
        elif (
            messageType == RequestDataType.CancelChatRequest
            or messageType == RequestDataType.CancelInlineCompletionRequest
        ):
            handlers = self._messageCallbackHandlers.get(messageId)
            if handlers is None:
                return
            handlers.cancel_token.cancel_request()

    def on_close(self):
        pass

    async def handle_inline_completions(
        prefix, suffix, language, filename, response_emitter, cancel_token
    ):
        if ai_service_manager.inline_completion_model is None:
            response_emitter.finish()
            return

        context = await ai_service_manager.get_completion_context(
            ContextRequest(
                ContextRequestType.InlineCompletion,
                prefix,
                suffix,
                language,
                filename,
                participant=ai_service_manager.get_chat_participant(prefix),
                cancel_token=cancel_token,
            )
        )

        if cancel_token.is_cancel_requested:
            response_emitter.finish()
            return

        completions = ai_service_manager.inline_completion_model.inline_completions(
            prefix, suffix, language, filename, context, cancel_token
        )
        if cancel_token.is_cancel_requested:
            response_emitter.finish()
            return

        response_emitter.stream({"completions": completions})
        response_emitter.finish()


class NotebookIntelligence(ExtensionApp):
    name = "lab_notebook_intelligence"
    default_url = "/lab-notebook-intelligence"
    load_other_extensions = True
    file_url_prefix = "/render"

    static_paths = []
    template_paths = []
    settings = {}
    handlers = []
    root_dir = ""

    notebook_execute_tool = Unicode(
        default_value="enabled",
        help="""
        Notebook execute tool options.

        'enabled' - Enable notebook execute tool (default).
        'disabled' - Disabled notebook execute tool.
        'env_enabled' - Disabled by default, can be enabled using 'NBI_NOTEBOOK_EXECUTE_TOOL=enabled'.
        """,
        allow_none=True,
        config=True,
    )

    def initialize_settings(self):
        pass

    def initialize_handlers(self):
        NotebookIntelligence.root_dir = self.serverapp.root_dir
        server_root_dir = os.path.expanduser(
            self.serverapp.web_app.settings["server_root_dir"]
        )
        self.initialize_ai_service(server_root_dir)
        self._setup_handlers(self.serverapp.web_app)
        self.serverapp.log.info(f"Registered {self.name} server extension")

    def initialize_ai_service(self, server_root_dir: str):
        global ai_service_manager
        ai_service_manager = AIServiceManager({"server_root_dir": server_root_dir})

    def initialize_templates(self):
        pass

    async def stop_extension(self):
        log.info(f"Stopping {self.name} extension...")
        github_copilot.handle_stop_request()

    def _setup_handlers(self, web_app):
        host_pattern = ".*$"

        base_url = web_app.settings["base_url"]
        route_pattern_capabilities = url_path_join(
            base_url, "lab-notebook-intelligence", "capabilities"
        )
        route_pattern_config = url_path_join(
            base_url, "lab-notebook-intelligence", "config"
        )
        route_pattern_update_provider_models = url_path_join(
            base_url, "lab-notebook-intelligence", "update-provider-models"
        )
        route_pattern_reload_mcp_servers = url_path_join(
            base_url, "lab-notebook-intelligence", "reload-mcp-servers"
        )
        route_pattern_mcp_config_file = url_path_join(
            base_url, "lab-notebook-intelligence", "mcp-config-file"
        )
        route_pattern_create_dynamic_mcp_config = url_path_join(
            base_url, "lab-notebook-intelligence", "create-dynamic-mcp-config"
        )
        route_pattern_emit_telemetry_event = url_path_join(
            base_url, "lab-notebook-intelligence", "emit-telemetry-event"
        )
        route_pattern_github_login_status = url_path_join(
            base_url, "lab-notebook-intelligence", "gh-login-status"
        )
        route_pattern_github_login = url_path_join(
            base_url, "lab-notebook-intelligence", "gh-login"
        )
        route_pattern_github_logout = url_path_join(
            base_url, "lab-notebook-intelligence", "gh-logout"
        )
        route_pattern_copilot = url_path_join(
            base_url, "lab-notebook-intelligence", "copilot"
        )
        GetCapabilitiesHandler.notebook_execute_tool = self.notebook_execute_tool
        NotebookIntelligence.handlers = [
            (route_pattern_capabilities, GetCapabilitiesHandler),
            (route_pattern_config, ConfigHandler),
            (route_pattern_update_provider_models, UpdateProviderModelsHandler),
            (route_pattern_reload_mcp_servers, ReloadMCPServersHandler),
            (route_pattern_mcp_config_file, MCPConfigFileHandler),
            (route_pattern_create_dynamic_mcp_config, CreateDynamicMCPConfigHandler),
            (route_pattern_emit_telemetry_event, EmitTelemetryEventHandler),
            (route_pattern_github_login_status, GetGitHubLoginStatusHandler),
            (route_pattern_github_login, PostGitHubLoginHandler),
            (route_pattern_github_logout, GetGitHubLogoutHandler),
            (route_pattern_copilot, WebsocketCopilotHandler),
        ]
        web_app.add_handlers(host_pattern, NotebookIntelligence.handlers)
