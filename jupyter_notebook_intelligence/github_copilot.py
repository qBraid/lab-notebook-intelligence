import json, time, requests, threading

EDITOR_VERSION = "Neovim/0.6.1"
EDITOR_PLUGIN_VERSION = "copilot.vim/1.16.0"
USER_AGENT = "GithubCopilot/1.155.0"
CLIENT_ID = "Iv1.b507a08c87ecfe98"

github_auth = {
    "verification_uri": None,
    "user_code": None,
    "device_code": None,
    "access_token": None,
    "token": None
}

def get_auth_status():
    global github_auth
    authenticated = github_auth["access_token"] is not None
    resp = {
        "authenticated": authenticated
    }
    if not authenticated:
        resp.update(get_device_verification_info())
        wait_for_tokens()
    
    return resp

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


    # Parse the response json, isolating the device_code, user_code, and verification_uri
    resp_json = resp.json()
    github_auth["verification_uri"] = resp_json.get('verification_uri')
    github_auth["user_code"] = resp_json.get('user_code')
    github_auth["device_code"] = resp_json.get('device_code')

    # user needs to visit the verification_uri and enter the user_code
    return {
        "verification_uri": github_auth["verification_uri"],
        "user_code": github_auth["user_code"]
    }

def wait_for_user_access_token_thread():
    global github_auth
    while True:
        time.sleep(5)
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

        # Parse the response json, isolating the access_token
        resp_json = resp.json()
        print(f"ACCESS TOKEN RESPONSE {resp_json}")
        access_token = resp_json.get('access_token')

        if access_token:
            github_auth["access_token"] = access_token
            print(f"ACCESS TOKEN RECEIVED {access_token}")
            break

def get_token():
    global github_auth
    access_token = github_auth["access_token"]

    resp = requests.get('https://api.github.com/copilot_internal/v2/token', headers={
        'authorization': f'token {access_token}',
        'editor-version': EDITOR_VERSION,
        'editor-plugin-version': EDITOR_PLUGIN_VERSION,
        'user-agent': USER_AGENT
    })

    resp_json = resp.json()
    token = resp_json.get('token')
    github_auth["token"] = token

def get_token_thread():
    while True:
        get_token()
        time.sleep(25 * 60)

def wait_for_tokens():
    threading.Thread(target=get_token_thread).start()
    threading.Thread(target=wait_for_user_access_token_thread).start()
