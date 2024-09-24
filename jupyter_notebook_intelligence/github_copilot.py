import json, time, requests, threading

EDITOR_VERSION = "Neovim/0.6.1"
EDITOR_PLUGIN_VERSION = "copilot.vim/1.16.0"
EDITOR_VERSION_CHAT = "vscode/1.83.1"
EDITOR_PLUGIN_VERSION_CHAT = "copilot-chat/0.8.0"
USER_AGENT = "GithubCopilot/1.155.0"
CLIENT_ID = "Iv1.b507a08c87ecfe98"

github_auth = {
    "verification_uri": None,
    "user_code": None,
    "device_code": None,
    "access_token": None,
    "token": None
}

IDE_NAME = "JupyterLab"
OS_TYPE = "Linux"

CHAT_SYSTEM_PROMPT = f"""
You are an AI programming assistant.
When asked for your name, you must respond with "GitHub Copilot".
Follow the user's requirements carefully & to the letter.
Follow Microsoft content policies.
Avoid content that violates copyrights.
If you are asked to generate content that is harmful, hateful, racist, sexist, lewd, violent, or completely irrelevant to software engineering, only respond with "Sorry, I can't assist with that."
Keep your answers short and impersonal.
You can answer general programming questions and perform the following tasks: 
* Ask a question about the files in your current workspace
* Explain how the code in your active editor works
* Generate unit tests for the selected code
* Propose a fix for the problems in the selected code
* Scaffold code for a new workspace
* Create a new Jupyter Notebook
* Find relevant code to your query
* Propose a fix for the a test failure
* Ask questions about {IDE_NAME}
* Generate query parameters for workspace search
* Ask how to do something in the terminal
* Explain what just happened in the terminal
You use the GPT-4 version of OpenAI's GPT models.
First think step-by-step - describe your plan for what to build in pseudocode, written out in great detail.
Then output the code in a single code block. This code block should not contain line numbers (line numbers are not necessary for the code to be understood, they are in format number: at beginning of lines).
Minimize any other prose.
Use Markdown formatting in your answers.
Make sure to include the programming language name at the start of the Markdown code blocks.
Avoid wrapping the whole response in triple backticks.
The user works in an IDE called {IDE_NAME} which has a concept for editors with open files, integrated unit test support, an output pane that shows the output of running the code as well as an integrated terminal.
The user is working on a {OS_TYPE} machine. Please respond with system specific commands if applicable.
The active document is the source code the user is looking at right now.
You can only give one reply for each conversation turn.
"""

get_token_thread = None

def get_login_status():
    global github_auth
    logged_in = github_auth["access_token"] is not None and github_auth["token"] is not None
    return {
        "logged_in": logged_in
    }

def login():
    login_info = get_device_verification_info()
    wait_for_tokens()
    return login_info

def get_device_verification_info():
    global github_auth
    data = {
        "client_id": CLIENT_ID,
        "scope":"read:user"
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

        if access_token:
            github_auth["access_token"] = access_token
            get_token()

def get_token():
    global github_auth
    access_token = github_auth["access_token"]

    if access_token is None:
        return

    resp = requests.get('https://api.github.com/copilot_internal/v2/token', headers={
        'authorization': f'token {access_token}',
        'editor-version': EDITOR_VERSION,
        'editor-plugin-version': EDITOR_PLUGIN_VERSION,
        'user-agent': USER_AGENT
    })

    resp_json = resp.json()
    token = resp_json.get('token')
    github_auth["token"] = token

def get_token_thread_func():
    while True:
        get_token()
        time.sleep(25 * 60)

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

    try:
        resp = requests.post('https://copilot-proxy.githubusercontent.com/v1/engines/copilot-codex/completions',
            headers={'authorization': f'Bearer {token}'},
                json={
                'prompt': prefix,
                'suffix': suffix,
                'max_tokens': 1000,
                'temperature': 0,
                'top_p': 1,
                'n': 1,
                'stop': ['\n'],
                'nwo': 'github/copilot.vim',
                'stream': True,
                'extra': {
                    'language': language
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
            else:
                result += '\n'
    
    return result

def chat(prompt):
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
                'messages': [
                    {"role": "system", "content": CHAT_SYSTEM_PROMPT},
                    {"role": "user", "content": "Active document is main.py"},
                    {"role": "user", "content": prompt}
                ],
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
