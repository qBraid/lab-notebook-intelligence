# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import json

from jupyter_server.base.handlers import APIHandler
from jupyter_server.utils import url_path_join
import requests
import tornado
import jupyter_notebook_intelligence.github_copilot as github_copilot


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

class PostInlineCompletionsHandler(APIHandler):
    @tornado.web.authenticated
    async def post(self):
        data = self.get_json_body()
        prefix = data['prefix']
        suffix = data['suffix']
        language = data['language']
        filename = data['filename']

        completions = github_copilot.inline_completions(prefix, suffix, language, filename)
        self.finish(json.dumps({
            "data": completions
        }))

class PostCompletionsHandler(APIHandler):
    @tornado.web.authenticated
    async def post(self):
        data = self.get_json_body()
        messages = data['messages']

        completions = github_copilot.completions(messages)
        self.finish(json.dumps({
            "data": completions
        }))

class PostChatHandler(APIHandler):
    @tornado.web.authenticated
    async def post(self):
        data = self.get_json_body()
        prompt = data['prompt']
        language = data['language']
        filename = data['filename']
        response = github_copilot.chat(prompt, language, filename)
        self.finish(json.dumps({
            "data": response
        }))

class PostExplainThisHandler(APIHandler):
    @tornado.web.authenticated
    async def post(self):
        data = self.get_json_body()
        selection = data['selection']
        language = data['language']
        filename = data['filename']
        response = github_copilot.explain_this(selection, language, filename)
        self.finish(json.dumps({
            "data": response
        }))

class PostFixThisHandler(APIHandler):
    @tornado.web.authenticated
    async def post(self):
        data = self.get_json_body()
        selection = data['selection']
        language = data['language']
        filename = data['filename']
        response = github_copilot.fix_this(selection, language, filename)
        self.finish(json.dumps({
            "data": response
        }))

class PostNewNotebookHandler(APIHandler):
    @tornado.web.authenticated
    async def post(self):
        data = self.get_json_body()
        prompt = data['prompt']
        parent_path = data['parent-path']
        response = github_copilot.new_notebook(prompt, parent_path)
        self.finish(json.dumps({
            "data": response
        }))

def setup_handlers(web_app):
    host_pattern = ".*$"

    base_url = web_app.settings["base_url"]
    route_pattern_github_login_status = url_path_join(base_url, "notebook-intelligence", "gh-login-status")
    route_pattern_github_login = url_path_join(base_url, "notebook-intelligence", "gh-login")
    route_pattern_inline_completions = url_path_join(base_url, "notebook-intelligence", "inline-completions")
    route_pattern_completions = url_path_join(base_url, "notebook-intelligence", "completions")
    route_pattern_chat = url_path_join(base_url, "notebook-intelligence", "chat")
    route_pattern_explain_this = url_path_join(base_url, "notebook-intelligence", "explain-this")
    route_pattern_fix_this = url_path_join(base_url, "notebook-intelligence", "fix-this")
    route_pattern_new_notebook = url_path_join(base_url, "notebook-intelligence", "new-notebook")
    handlers = [
        (route_pattern_github_login_status, GetGitHubLoginStatusHandler),
        (route_pattern_github_login, PostGitHubLoginHandler),
        (route_pattern_inline_completions, PostInlineCompletionsHandler),
        (route_pattern_completions, PostCompletionsHandler),
        (route_pattern_chat, PostChatHandler),
        (route_pattern_explain_this, PostExplainThisHandler),
        (route_pattern_fix_this, PostFixThisHandler),
        (route_pattern_new_notebook, PostNewNotebookHandler),
    ]
    web_app.add_handlers(host_pattern, handlers)
