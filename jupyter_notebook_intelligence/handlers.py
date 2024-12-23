# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import json
from os import path
import os
import sys

from jupyter_server.base.handlers import APIHandler
from jupyter_server.utils import url_path_join
import tornado
import traitlets
from jupyter_notebook_intelligence.agents import AgentManager, ChatRequest, NotebookIntelligenceChatAgent, NotebookIntelligenceExtension
from jupyter_notebook_intelligence.config import ContextInputFileInfo, ContextRequest, ContextType, NotebookIntelligenceConfig
import jupyter_notebook_intelligence.github_copilot as github_copilot

agent_manager: AgentManager = None

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

        response = agent_manager.handle_chat_request(ChatRequest(prompt))
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

def load_extension(extension_class: str) -> NotebookIntelligenceExtension:
    import importlib
    try:
        parts = extension_class.split(".")
        module_name = ".".join(parts[0:-1])
        class_name = parts[-1]
        ExtensionClass = getattr(importlib.import_module(module_name), class_name)
        if ExtensionClass is not None and issubclass(ExtensionClass, NotebookIntelligenceExtension):
            instance = ExtensionClass()
            return instance
    except:
        pass

    return None

def initialize_extensions():
    global agent_manager
    default_chat_agent = github_copilot.GithubCopilotChatAgent()
    agent_manager = AgentManager(default_chat_agent)
    extensions_dir = path.join(sys.prefix, "share", "jupyter", "nbiextensions")
    subfolders = [f.path for f in os.scandir(extensions_dir) if f.is_dir()]
    for extension_dir in list(subfolders):
        metadata_path = path.join(extension_dir, "extension.json")
        if path.exists(metadata_path) and path.isfile(metadata_path):
            with open(metadata_path, 'r') as file:
                data = json.load(file)
                class_name = data['class']
                extension = load_extension(class_name)
                if extension:
                    for chat_agent in extension.chat_agents:
                        agent_manager.register_chat_agent(chat_agent)

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
        (route_pattern_chat, PostChatHandler),
        (route_pattern_explain_this, PostExplainThisHandler),
        (route_pattern_fix_this, PostFixThisHandler),
        (route_pattern_new_notebook, PostNewNotebookHandler),
    ]
    web_app.add_handlers(host_pattern, handlers)
