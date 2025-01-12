# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>
#
# GitHub auth and inline completion sections are derivative of https://github.com/B00TK1D/copilot-api

from dataclasses import dataclass
from enum import Enum
import os, json, time, requests, threading
from pathlib import Path
import uuid
import secrets
import sseclient
import datetime as dt
from notebook_intelligence.extension import ChatCommand, ChatResponse, ChatRequest, ChatParticipant, CompletionContext, MarkdownData, Tool
from notebook_intelligence.github_copilot_prompts import CopilotPrompts

from ._version import __version__ as NBI_VERSION

EDITOR_VERSION = f"NotebookIntelligence/{NBI_VERSION}"
EDITOR_PLUGIN_VERSION = f"NotebookIntelligence/{NBI_VERSION}"
USER_AGENT = f"NotebookIntelligence/{NBI_VERSION}"
CLIENT_ID = "Iv1.b507a08c87ecfe98"
MACHINE_ID = secrets.token_hex(33)[0:65]

API_ENDPOINT = "https://api.githubcopilot.com"
PROXY_ENDPOINT = "https://copilot-proxy.githubusercontent.com"
TOKEN_REFRESH_INTERVAL = 1500
ACCESS_TOKEN_THREAD_SLEEP_INTERVAL = 5
TOKEN_THREAD_SLEEP_INTERVAL = 3
TOKEN_FETCH_INTERVAL = 15
NL = '\n'

LoginStatus = Enum('LoginStatus', ['NOT_LOGGED_IN', 'ACTIVATING_DEVICE', 'LOGGING_IN', 'LOGGED_IN'])

github_auth = {
    "verification_uri": None,
    "user_code": None,
    "device_code": None,
    "access_token": None,
    "status" : LoginStatus.NOT_LOGGED_IN,
    "token": None,
    "token_expires_at": dt.datetime.now()
}

stop_requested = False
get_access_code_thread = None
get_token_thread = None
last_token_fetch_time = dt.datetime.now() + dt.timedelta(seconds=-TOKEN_FETCH_INTERVAL)

def get_login_status():
    global github_auth

    response = {
        "status": github_auth["status"].name
    }
    if github_auth["status"] is LoginStatus.ACTIVATING_DEVICE:
        response.update({
            "verification_uri": github_auth["verification_uri"],
            "user_code": github_auth["user_code"]
        })

    return response

def login():
    login_info = get_device_verification_info()
    wait_for_tokens()
    return login_info

def logout():
    global github_auth
    github_auth.update({
        "verification_uri": None,
        "user_code": None,
        "device_code": None,
        "access_token": None,
        "status" : LoginStatus.NOT_LOGGED_IN,
        "token": None
    })

    return {
        "status": github_auth["status"].name
    }

def handle_stop_request():
    global stop_requested
    stop_requested = True

def get_device_verification_info():
    global github_auth
    data = {
        "client_id": CLIENT_ID,
        "scope": "read:user"
    }
    resp = requests.post('https://github.com/login/device/code',
        headers={
            'accept': 'application/json',
            'editor-version': EDITOR_VERSION,
            'editor-plugin-version': EDITOR_PLUGIN_VERSION,
            'content-type': 'application/json',
            'user-agent': USER_AGENT,
            'accept-encoding': 'gzip,deflate,br'
        },
        data=json.dumps(data)
    )

    resp_json = resp.json()
    github_auth["verification_uri"] = resp_json.get('verification_uri')
    github_auth["user_code"] = resp_json.get('user_code')
    github_auth["device_code"] = resp_json.get('device_code')

    github_auth["status"] = LoginStatus.ACTIVATING_DEVICE

    # user needs to visit the verification_uri and enter the user_code
    return {
        "verification_uri": github_auth["verification_uri"],
        "user_code": github_auth["user_code"]
    }

def wait_for_user_access_token_thread_func():
    global github_auth, get_access_code_thread

    token_from_env = os.environ.get("GITHUB_ACCESS_TOKEN", None)

    if token_from_env is not None:
        print("Setting GitHub access token from environment variable")
        github_auth["access_token"] = token_from_env
        get_access_code_thread = None
        return

    while True:
        # terminate thread if logged out or stop requested
        if stop_requested or github_auth["access_token"] is not None or github_auth["device_code"] is None or github_auth["status"] == LoginStatus.NOT_LOGGED_IN:
            get_access_code_thread = None
            break
        data = {
            "client_id": CLIENT_ID,
            "device_code": github_auth["device_code"],
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code"
        }
        resp = requests.post('https://github.com/login/oauth/access_token',
            headers={
            'accept': 'application/json',
            'editor-version': EDITOR_VERSION,
            'editor-plugin-version': EDITOR_PLUGIN_VERSION,
            'content-type': 'application/json',
            'user-agent': USER_AGENT,
            'accept-encoding': 'gzip,deflate,br'
            },
            data=json.dumps(data)
        )

        resp_json = resp.json()
        access_token = resp_json.get('access_token')
        # print(f"ACCESS TOKEN {access_token}")

        if access_token:
            github_auth["access_token"] = access_token
            get_token()
            get_access_code_thread = None
            break

        time.sleep(ACCESS_TOKEN_THREAD_SLEEP_INTERVAL)

def get_token():
    global github_auth, API_ENDPOINT, PROXY_ENDPOINT, TOKEN_REFRESH_INTERVAL
    access_token = github_auth["access_token"]

    if access_token is None:
        return

    github_auth["status"] = LoginStatus.LOGGING_IN

    resp = requests.get('https://api.github.com/copilot_internal/v2/token', headers={
        'authorization': f'token {access_token}',
        'editor-version': EDITOR_VERSION,
        'editor-plugin-version': EDITOR_PLUGIN_VERSION,
        'user-agent': USER_AGENT
    })

    resp_json = resp.json()
    token = resp_json.get('token')
    github_auth["token"] = token
    expires_at = resp_json.get('expires_at')
    if expires_at is not None:
        github_auth["token_expires_at"] = dt.datetime.fromtimestamp(expires_at)
    else:
        github_auth["token_expires_at"] = dt.datetime.now() + dt.timedelta(seconds=TOKEN_REFRESH_INTERVAL)
    github_auth["verification_uri"] = None
    github_auth["user_code"] = None
    github_auth["status"] = LoginStatus.LOGGED_IN

    endpoints = resp_json.get('endpoints', {})
    API_ENDPOINT = endpoints.get('api', API_ENDPOINT)
    PROXY_ENDPOINT = endpoints.get('proxy', PROXY_ENDPOINT)
    TOKEN_REFRESH_INTERVAL = resp_json.get('refresh_in', TOKEN_REFRESH_INTERVAL)

def get_token_thread_func():
    global github_auth, get_token_thread, last_token_fetch_time
    while True:
        # terminate thread if logged out or stop requested
        if stop_requested or github_auth["status"] == LoginStatus.NOT_LOGGED_IN:
            get_token_thread = None
            return
        token = github_auth["token"]
        # update token if 10 seconds or less left to expiration
        if github_auth["access_token"] is not None and (token is None or (dt.datetime.now() - github_auth["token_expires_at"]).total_seconds() > -10):
            if (dt.datetime.now() - last_token_fetch_time).total_seconds() > TOKEN_FETCH_INTERVAL:
                print("Refreshing token")
                get_token()
                last_token_fetch_time = dt.datetime.now()

        time.sleep(TOKEN_THREAD_SLEEP_INTERVAL)

def wait_for_tokens():
    global get_access_code_thread, get_token_thread
    if get_access_code_thread is None:
        get_access_code_thread = threading.Thread(target=wait_for_user_access_token_thread_func)
        get_access_code_thread.start()

    if get_token_thread is None:
        get_token_thread = threading.Thread(target=get_token_thread_func)
        get_token_thread.start()

def _generate_copilot_headers():
    global github_auth
    token = github_auth['token']

    return {
        'authorization': f'Bearer {token}',
        'editor-version': EDITOR_VERSION,
        'editor-plugin-version': EDITOR_PLUGIN_VERSION,
        'user-agent': USER_AGENT,
        'content-type': 'application/json',
        'openai-intent': 'conversation-panel',
        'openai-organization': 'github-copilot',
        'copilot-integration-id': 'vscode-chat',
        'x-request-id': str(uuid.uuid4()),
        'vscode-sessionid': str(uuid.uuid4()),
        'vscode-machineid': MACHINE_ID,
    }

def inline_completions(prefix, suffix, language, filename, context: CompletionContext):
    global github_auth
    token = github_auth['token']

    prompt = f"# Path: {filename}"

    if context is not None:
        for item in context.items:
            context_file = f"Compare this snippet from {item.file_path if item.file_path is not None else 'undefined'}:{NL}{item.content}{NL}"
            prompt += "\n# " + "\n# ".join(context_file.split('\n'))

    prompt += f"{NL}{prefix}"

    try:
        resp = requests.post(f"{PROXY_ENDPOINT}/v1/engines/copilot-codex/completions",
            headers={'authorization': f'Bearer {token}'},
                json={
                'prompt': prompt,
                'suffix': suffix,
                'min_tokens': 500,
                'max_tokens': 2000,
                'temperature': 0,
                'top_p': 1,
                'n': 1,
                'stop': ['<END>', '```'],
                'nwo': 'NotebookIntelligence',
                'stream': True,
                'extra': {
                    'language': language,
                    'next_indent': 0,
                    'trim_by_indentation': True
                }
            }
        )
    except requests.exceptions.ConnectionError:
        return ''

    result = ''

    resp_text = resp.text.split('\n')
    for line in resp_text:
        if line.startswith('data: {'):
            json_completion = json.loads(line[6:])
            completion = json_completion.get('choices')[0].get('text')
            if completion:
                result += completion
            # else:
            #     result += '\n'
    
    return result

def completions(messages, tools = None, response: ChatResponse = None, options: dict = {}):
    stream = response is not None

    try:
        data = {
            'messages': messages,
            'tools': tools,
            'max_tokens': 1000,
            'temperature': 0,
            'top_p': 1,
            'n': 1,
            'stop': ['<END>'],
            'nwo': 'NotebookIntelligence',
            'stream': stream
        }

        if 'tool_choice' in options:
            data['tool_choice'] = options['tool_choice']

        request = requests.post(
            f"{API_ENDPOINT}/chat/completions",
            headers = _generate_copilot_headers(),
            json = data,
            stream = stream
        )

        if stream:
            client = sseclient.SSEClient(request)
            for event in client.events():
                if event.data == '[DONE]':
                    response.finish()
                else:
                    response.stream(json.loads(event.data))
            return
        else:
            return request.json()
    except requests.exceptions.ConnectionError:
        raise Exception("Connection error")

def _get_unique_notebook_name(parent_path, name):
    if parent_path.startswith("~"):
        parent_path = os.path.expanduser(parent_path)

    tried = 0

    while True:
        suffix = "" if tried == 0 else f"{tried + 1}"
        notebook_name = f"{name}{suffix}.ipynb"
        file_path = Path(os.path.join(parent_path, notebook_name))
        if not file_path.exists():
            return notebook_name
        tried += 1

class AddMarkdownCellToNotebookTool(Tool):
    @property
    def name(self) -> str:
        return "add_markdown_cell_to_notebook"

    @property
    def title(self) -> str:
        return "Add markdown cell to notebook"
    
    @property
    def tags(self) -> list[str]:
        return ["default-participant-tool"]
    
    @property
    def description(self) -> str:
        return "This is a tool that adds markdown cell to a notebook"
    
    @property
    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "markdown_cell_source": {
                            "type": "string",
                            "description": "Markdown to add to the notebook",
                        }
                    },
                    "required": ["markdown_cell_source"],
                    "additionalProperties": False,
                },
            },
        }

    async def handle_tool_call(self, request: ChatRequest, response: ChatResponse, tool_context: dict, tool_args: dict) -> dict:
        markdown = tool_args.get('markdown_cell_source')
        ui_cmd_response = await response.run_ui_command('notebook-intelligence:add-markdown-cell-to-notebook', {'markdown': markdown, 'path': tool_context.get('file_path')})
        return {}

class AddCodeCellTool(Tool):
    @property
    def name(self) -> str:
        return "add_code_cell_to_notebook"

    @property
    def title(self) -> str:
        return "Add code cell to notebook"
    
    @property
    def tags(self) -> list[str]:
        return ["default-participant-tool"]
    
    @property
    def description(self) -> str:
        return "This is a tool that adds code cell to a notebook"
    
    @property
    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code_cell_source": {
                            "type": "string",
                            "description": "Code to add to the notebook",
                        }
                    },
                    "required": ["code_cell_source"],
                    "additionalProperties": False,
                },
            },
        }

    async def handle_tool_call(self, request: ChatRequest, response: ChatResponse, tool_context: dict, tool_args: dict) -> dict:
        code = tool_args.get('code_cell_source')
        ui_cmd_response = await response.run_ui_command('notebook-intelligence:add-code-cell-to-notebook', {'code': code, 'path': tool_context.get('file_path')})
        return {}

class GithubCopilotChatParticipant(ChatParticipant):
    @property
    def id(self) -> str:
        return "default"
    
    @property
    def commands(self) -> list[ChatCommand]:
        return [
            ChatCommand(name='newNotebook', description='Create a new notebook'),
            ChatCommand(name='newPythonFile', description='Create a new Python file'),
            ChatCommand(name='clear', description='Clears chat history'),
        ]

    @property
    def tools(self) -> list[Tool]:
        return [AddMarkdownCellToNotebookTool(), AddCodeCellTool()]

    @property
    def allowed_context_providers(self) -> set[str]:
        # any context provider can be used
        return set(["*"])

    async def handle_chat_request(self, request: ChatRequest, response: ChatResponse, options: dict = {}) -> None:
        if request.command == 'newNotebook':
            # create a new notebook
            ui_cmd_response = await response.run_ui_command('notebook-intelligence:create-new-notebook-from-py', {'code': ''})
            file_path = ui_cmd_response['path']
            tool_names = [tool.name for tool in self.tools]
            request.chat_history.insert(0, {"role": "system", "content": f"You are an assistant that creates Jupyter notebooks. Use the functions provided to add markdown or code cells to the notebook. Code cells are written in Python. Markdown cells are written in Markdown. Call the functions with either Python or Markdown content. Do not repeat the code in the code cells with markdown explanations. You have only two functions available to you: '{tool_names[0]}' and '{tool_names[1]}'. Do not assume the availibility of any other tools or functions. Make sure to generate at least one code cell and one markdown cell."})
            await self.handle_chat_request_with_tools(request, response, options, tool_context={
                'file_path': file_path
            }, tool_choice='required')
            return
        elif request.command == 'newPythonFile':
            # create a new notebook
            messages = [
                {"role": "system", "content": f"You are an assistant that creates Python code. You should return the code directly without any explantion. You should not print message to explain the code or purpose of the code. You should return the code directly, without wrapping it inside ```."},
                {"role": "user", "content": f"Generate code for: {request.prompt}"}
            ]
            generated = completions(messages)
            code = generated['choices'][0]['message']['content']
            ui_cmd_response = await response.run_ui_command('notebook-intelligence:create-new-file', {'code': code })
            file_path = ui_cmd_response['path']
            response.stream(MarkdownData(f"File '{file_path}' created successfully"))
            response.finish()
            return

        messages = [
            {"role": "system", "content": options.get("system_prompt", CopilotPrompts.chat_prompt())},
        ] + request.chat_history

        completions(messages, response=response)
