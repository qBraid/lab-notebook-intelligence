# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import json
import os

class NBIConfig:
    def __init__(self):
        self.config_file = os.path.join(os.path.expanduser('~'), ".jupyter", "nbi-config.json")
        self.config = {}
        self.load()

    def load(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as file:
                self.config = json.load(file)
        else:
            self.config = {}

    def save(self):
        with open(self.config_file, 'w') as file:
            json.dump(self.config, file, indent=4)

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save()

    @property
    def chat_model(self):
        return self.get('chat_model', {'provider': 'github-copilot', 'model': 'gpt-4o'})

    @property
    def inline_completion_model(self):
        return self.get('inline_completion_model', {'provider': 'github-copilot', 'model': 'copilot-codex'})

    @property
    def embedding_model_id(self):
        return self.get('embedding_model_id', '')

    @property
    def using_github_copilot_service(self) -> bool:
        return self.chat_model.get("provider") == 'github-copilot' or \
            self.inline_completion_model.get("provider") == 'github-copilot'
