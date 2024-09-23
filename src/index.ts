import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';

import { ISettingRegistry } from '@jupyterlab/settingregistry';

import { requestAPI } from './handler';

/**
 * Initialization data for the @mbektas/jupyter-notebook-intelligence extension.
 */
const plugin: JupyterFrontEndPlugin<void> = {
  id: '@mbektas/jupyter-notebook-intelligence:plugin',
  description: 'Jupyter Notebook Intelligence extension',
  autoStart: true,
  optional: [ISettingRegistry],
  activate: (app: JupyterFrontEnd, settingRegistry: ISettingRegistry | null) => {
    console.log('JupyterLab extension @mbektas/jupyter-notebook-intelligence is activated!');

    if (settingRegistry) {
      settingRegistry
        .load(plugin.id)
        .then(settings => {
          console.log('@mbektas/jupyter-notebook-intelligence settings loaded:', settings.composite);
        })
        .catch(reason => {
          console.error('Failed to load settings for @mbektas/jupyter-notebook-intelligence.', reason);
        });
    }

    let ghLoginRequested = false;
    let ghAuthenticated = false;

    const loginToGitHub = () => {
      requestAPI<any>('gh-login', {method: 'POST'})
      .then(data => {
        console.log(`Login to GitHub Copilot using ${data.verification_uri} and device code ${data.user_code}`);
      })
      .catch(reason => {
        console.error(
          `The jupyter_notebook_intelligence server extension appears to be missing.\n${reason}`
        );
      });
    };

    const getGitHubLoginStatus = () => {
      requestAPI<any>('gh-login-status')
      .then(data => {
        ghAuthenticated = data.logged_in;
        if (!ghAuthenticated && !ghLoginRequested) {
          loginToGitHub();
          ghLoginRequested = true;
        }
      })
      .catch(reason => {
        console.error(
          `The jupyter_notebook_intelligence server extension appears to be missing.\n${reason}`
        );
      });
    };

    setInterval(() => {
      getGitHubLoginStatus();
    }, 5000);

    getGitHubLoginStatus();

    // const testChat = () => {
    //   requestAPI<any>('chat', { method: 'POST', body: JSON.stringify({})})
    //   .then(data => {
    //     console.log(`CHAT RESPONSE\n${data}`);
    //   })
    //   .catch(reason => {
    //     console.error(
    //       `The jupyter_notebook_intelligence server extension appears to be missing.\n${reason}`
    //     );
    //   });
    // };

    const testInlineCompletions = () => {
      requestAPI<any>('inline-completions', {
        method: 'POST',
        body: JSON.stringify({
          prefix: 'def print_hello_world():\n',
          suffix: '',
          language: 'python'
        })}
      )
      .then(data => {
        console.log(`INLINE COMPLETIONS RESPONSE\n${data}`);
      })
      .catch(reason => {
        console.error(
          `The jupyter_notebook_intelligence server extension appears to be missing.\n${reason}`
        );
      });
    };


    setInterval(() => {
      if (ghAuthenticated) {
        // testChat();
        testInlineCompletions();
      }
    }, 10000);
  }
};

export default plugin;
