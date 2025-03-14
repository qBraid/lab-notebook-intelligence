# Notebook Intelligence

Notebook Intelligence (NBI) is an AI coding assistant and extensible AI framework for JupyterLab. It can use GitHub Copilot or AI models from any other LLM Provider, including local models from [Ollama](https://ollama.com/). NBI greatly boosts the productivity of JupyterLab users with AI assistance.

See blog posts for features and usage.

- [Introducing Notebook Intelligence!](https://notebook-intelligence.github.io/notebook-intelligence/blog/2025/01/08/introducing-notebook-intelligence.html)
- [Building AI Extensions for JupyterLab](https://notebook-intelligence.github.io/notebook-intelligence/blog/2025/02/05/building-ai-extensions-for-jupyterlab.html)
- [Building AI Agents for JupyterLab](https://notebook-intelligence.github.io/notebook-intelligence/blog/2025/02/09/building-ai-agents-for-jupyterlab.html)
- [Notebook Intelligence now supports any LLM Provider and AI Model!](https://notebook-intelligence.github.io/notebook-intelligence/blog/2025/03/05/support-for-any-llm-provider.html)

### Code generation with inline chat

![Generate code](media/generate-code.gif)

### Auto-complete

<img src="media/inline-completion.gif" alt="Auto-complete" width=700 />

### Chat interface

<img src="media/copilot-chat.gif" alt="Chat interface" width=600 />

[![Github Actions Status](https://github.com/notebook-intelligence/notebook-intelligence/workflows/Build/badge.svg)](https://github.com/notebook-intelligence/notebook-intelligence/actions/workflows/build.yml)

## Configuring LLM Provider and models

You can configure the model provider and model options using the Notebook Intelligence Settings dialog. You can access this dialog from JupyterLab Settings menu -> Notebook Intelligence Settings, using `/settings` command in Copilot Chat or by using the command palette. For more details, see the [blog post](https://notebook-intelligence.github.io/notebook-intelligence/blog/2025/03/05/support-for-any-llm-provider.html).

<img src="media/provider-list.png" alt="Settings dialog" width=500 />

Notebook Intelligence extension for JupyterLab

This extension is composed of a Python package named `notebook_intelligence`
for the server extension and a NPM package named `@notebook-intelligence/notebook-intelligence`
for the frontend extension.

## Requirements

- JupyterLab >= 4.0.0

## Install

To install the extension, execute:

```bash
pip install notebook_intelligence
```

## Uninstall

To remove the extension, execute:

```bash
pip uninstall notebook_intelligence
```

## Configuration options

### Remembering GitHub Copilot login

Notebook Intelligence uses system keyring to store the GitHub access tokens. If your stored access token fails to login (due to expiration or other reasons), you will be prompted to relogin on the UI. If you run into issues with this feature, check the Jupyter server logs and the [keyring package](https://github.com/jaraco/keyring) documentation.

To let Notebook Intelligence remember your GitHub access token after you logged in:

```bash
jupyter lab --NotebookIntelligence.github_access_token=remember
```

Once you set it to remember, it will continue to remember even if you skip `--NotebookIntelligence.github_access_token` at following launches. In order to forget the GitHub access token stored:

```bash
jupyter lab --NotebookIntelligence.github_access_token=forget
```

## Troubleshoot

If you are seeing the frontend extension, but it is not working, check
that the server extension is enabled:

```bash
jupyter server extension list
```

If the server extension is installed and enabled, but you are not seeing
the frontend extension, check the frontend extension is installed:

```bash
jupyter labextension list
```

## Contributing

### Development install

Note: You will need NodeJS to build the extension package.

The `jlpm` command is JupyterLab's pinned version of
[yarn](https://yarnpkg.com/) that is installed with JupyterLab. You may use
`yarn` or `npm` in lieu of `jlpm` below.

```bash
# Clone the repo to your local environment
# Change directory to the notebook_intelligence directory
# Install package in development mode
pip install -e "."
# Link your development version of the extension with JupyterLab
jupyter labextension develop . --overwrite
# Server extension must be manually installed in develop mode
jupyter server extension enable notebook_intelligence
# Rebuild extension Typescript source after making changes
jlpm build
```

You can watch the source directory and run JupyterLab at the same time in different terminals to watch for changes in the extension's source and automatically rebuild the extension.

```bash
# Watch the source directory in one terminal, automatically rebuilding when needed
jlpm watch
# Run JupyterLab in another terminal
jupyter lab
```

With the watch command running, every saved change will immediately be built locally and available in your running JupyterLab. Refresh JupyterLab to load the change in your browser (you may need to wait several seconds for the extension to be rebuilt).

By default, the `jlpm build` command generates the source maps for this extension to make it easier to debug using the browser dev tools. To also generate source maps for the JupyterLab core extensions, you can run the following command:

```bash
jupyter lab build --minimize=False
```

### Development uninstall

```bash
# Server extension must be manually disabled in develop mode
jupyter server extension disable notebook_intelligence
pip uninstall notebook_intelligence
```

In development mode, you will also need to remove the symlink created by `jupyter labextension develop`
command. To find its location, you can run `jupyter labextension list` to figure out where the `labextensions`
folder is located. Then you can remove the symlink named `@notebook-intelligence/notebook-intelligence` within that folder.

### Packaging the extension

See [RELEASE](RELEASE.md)

### Resources I used as reference

- [Copilot Internals blog post](https://thakkarparth007.github.io/copilot-explorer/posts/copilot-internals.html)
- [B00TK1D/copilot-api for GitHub auth and inline completions](https://github.com/B00TK1D/copilot-api)
