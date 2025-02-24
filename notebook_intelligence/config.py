# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import json
import os

class NBIConfig:
    def __init__(self):
        self.config_file = os.path.join(os.path.expanduser('~'), ".jupyter", "nbi-config.json")
        self.settings = {}
        self.load()

    def load(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as file:
                self.settings = json.load(file)
        else:
            self.settings = {}

    def save(self):
        with open(self.config_file, 'w') as file:
            json.dump(self.settings, file, indent=4)

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = value
        self.save()

    @property
    def chat_model(self):
        return self.get('chat_model', 'github-copilot::gpt-4o')
    
    @chat_model.setter
    def chat_model(self, value):
        self.set('chat_model', value)

    @property
    def openai_compatible_chat_model_id(self):
        return self.get('openai_compatible_chat_model_id', '')
    
    @openai_compatible_chat_model_id.setter
    def openai_compatible_chat_model_id(self, value):
        self.set('openai_compatible_chat_model_id', value)

    @property
    def openai_compatible_chat_model_base_url(self):
        return self.get('openai_compatible_chat_model_base_url', '')
    
    @openai_compatible_chat_model_base_url.setter
    def openai_compatible_chat_model_base_url(self, value):
        self.set('openai_compatible_chat_model_base_url', value)

    @property
    def openai_compatible_chat_model_api_key(self):
        return self.get('openai_compatible_chat_model_api_key', '')
    
    @openai_compatible_chat_model_api_key.setter
    def openai_compatible_chat_model_api_key(self, value):
        self.set('openai_compatible_chat_model_api_key', value)

    @property
    def inline_completion_model(self):
        return self.get('inline_completion_model', 'github-copilot::copilot-codex')
    
    @inline_completion_model.setter
    def inline_completion_model(self, value):
        self.set('inline_completion_model', value)

    @property
    def openai_compatible_inline_completion_model_id(self):
        return self.get('openai_compatible_inline_completion_model_id', '')
    
    @openai_compatible_inline_completion_model_id.setter
    def openai_compatible_inline_completion_model_id(self, value):
        self.set('openai_compatible_inline_completion_model_id', value)

    @property
    def openai_compatible_inline_completion_model_base_url(self):
        return self.get('openai_compatible_inline_completion_model_base_url', '')
    
    @openai_compatible_inline_completion_model_base_url.setter
    def openai_compatible_inline_completion_model_base_url(self, value):
        self.set('openai_compatible_inline_completion_model_base_url', value)

    @property
    def openai_compatible_inline_completion_model_api_key(self):
        return self.get('openai_compatible_inline_completion_model_api_key', '')
    
    @openai_compatible_inline_completion_model_api_key.setter
    def openai_compatible_inline_completion_model_api_key(self, value):
        self.set('openai_compatible_inline_completion_model_api_key', value)

    @property
    def embedding_model_id(self):
        return self.get('embedding_model_id', '')
    
    @embedding_model_id.setter
    def embedding_model_id(self, value):
        self.set('embedding_model_id', value)

    @property
    def using_github_copilot_service(self) -> bool:
        return self.chat_model.startswith('github-copilot::') or self.inline_completion_model.startswith('github-copilot::')
