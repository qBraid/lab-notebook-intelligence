# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

from enum import Enum
import json, time, requests, threading
from jupyter_notebook_intelligence.github_copilot_prompts import CopilotPrompts

EDITOR_VERSION = "Neovim/0.6.1"
EDITOR_PLUGIN_VERSION = "copilot.vim/1.16.0"
EDITOR_VERSION_CHAT = "vscode/1.83.1"
EDITOR_PLUGIN_VERSION_CHAT = "copilot-chat/0.8.0"
USER_AGENT = "GithubCopilot/1.155.0"
CLIENT_ID = "Iv1.b507a08c87ecfe98"

LoginStatus = Enum('LoginStatus', ['NOT_LOGGED_IN', 'ACTIVATING_DEVICE', 'LOGGING_IN', 'LOGGED_IN'])

github_auth = {
    "verification_uri": None,
    "user_code": None,
    "device_code": None,
    "access_token": None,
    "status" : LoginStatus.NOT_LOGGED_IN,
    "token": None
}

get_token_thread = None

def get_login_status():
    global github_auth

    return {
        "status": github_auth["status"].name
    }

def login():
    login_info = get_device_verification_info()
    wait_for_tokens()
    return login_info

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
    global github_auth

    while True:
        if github_auth["access_token"] is not None:
            break
        time.sleep(15)
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

def get_token():
    global github_auth
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
    github_auth["status"] = LoginStatus.LOGGED_IN

def get_token_thread_func():
    global github_auth
    while True:
        get_token()
        token = github_auth["token"]
        wait_time = 15 if token is None else 25 * 60 
        time.sleep(wait_time)

def wait_for_tokens():
    global get_token_thread
    if github_auth["access_token"] is None:
        threading.Thread(target=wait_for_user_access_token_thread_func).start()

    if get_token_thread is None:
        get_token_thread = threading.Thread(target=get_token_thread_func)
        get_token_thread.start()

def inline_completions(prefix, suffix, language):
    global github_auth
    token = github_auth['token']

    prompt = f"# Path: main.py\n{prefix}"

    try:
        resp = requests.post('https://copilot-proxy.githubusercontent.com/v1/engines/copilot-codex/completions',
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
                'nwo': 'github/copilot.vim',
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

def completions(messages):
    global github_auth
    token = github_auth['token']

    try:
        resp = requests.post(
            'https://api.githubcopilot.com/chat/completions',
            headers={
                'authorization': f'Bearer {token}',
                'editor-version': EDITOR_VERSION_CHAT,
                'editor-plugin-version': EDITOR_PLUGIN_VERSION_CHAT
            },
            json={
                'messages': messages,
                'max_tokens': 1000,
                'temperature': 0,
                'top_p': 1,
                'n': 1,
                'stop': ['<END>'],
                'nwo': 'github/copilot.vim',
                'stream': False,
            }
        )
    except requests.exceptions.ConnectionError:
        return ''

    response = resp.json()
    return {"message": response["choices"][0]["message"]["content"]}

def chat(prompt):
    messages = [
        {"role": "system", "content": CopilotPrompts.chat_prompt()},
        {"role": "user", "content": "Active document is main.py"},
        {"role": "user", "content": prompt}
    ]
    return completions(messages)

def explain_this(selection):
    messages = [
        {"role": "system", "content": CopilotPrompts.explain_this_prompt()},
        {"role": "user", "content": "Active document is main.py\nActive selection is"},
        {"role": "user", "content": selection}
    ]
    return completions(messages)

def fix_this(selection):
    messages = [
        {"role": "system", "content": CopilotPrompts.fix_this_prompt()},
        {"role": "user", "content": "Active document is main.py\nActive selection is"},
        {"role": "user", "content": selection}
    ]
    return completions(messages)
