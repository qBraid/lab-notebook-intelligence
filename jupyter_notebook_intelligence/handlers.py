import json

from jupyter_server.base.handlers import APIHandler
from jupyter_server.utils import url_path_join
import tornado
from jupyter_notebook_intelligence.github_copilot import get_auth_status

class GetGitHubAuthStatusHandler(APIHandler):
    # The following decorator should be present on all verb methods (head, get, post,
    # patch, put, delete, options) to ensure only authorized user can request the
    # Jupyter server
    @tornado.web.authenticated
    def get(self):
        self.finish(json.dumps(get_auth_status()))

class PostChatHandler(APIHandler):
    # The following decorator should be present on all verb methods (head, get, post,
    # patch, put, delete, options) to ensure only authorized user can request the
    # Jupyter server
    @tornado.web.authenticated
    def post(self):
        self.finish(json.dumps({
            "data": "This is /notebook-intelligence/chat endpoint!"
        }))

class PostInlineCompletionsHandler(APIHandler):
    # The following decorator should be present on all verb methods (head, get, post,
    # patch, put, delete, options) to ensure only authorized user can request the
    # Jupyter server
    @tornado.web.authenticated
    def post(self):
        self.finish(json.dumps({
            "data": "This is /notebook-intelligence/inline-completions endpoint!"
        }))

def setup_handlers(web_app):
    host_pattern = ".*$"

    base_url = web_app.settings["base_url"]
    route_pattern_github_auth_status = url_path_join(base_url, "notebook-intelligence", "gh-auth-status")
    route_pattern_chat = url_path_join(base_url, "notebook-intelligence", "chat")
    route_pattern_inline_completions = url_path_join(base_url, "notebook-intelligence", "inline-completions")
    handlers = [
        (route_pattern_github_auth_status, GetGitHubAuthStatusHandler),
        (route_pattern_chat, PostChatHandler),
        (route_pattern_inline_completions, PostInlineCompletionsHandler),
    ]
    web_app.add_handlers(host_pattern, handlers)
