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

    requestAPI<any>('chat', {method: 'POST', body: '{}'})
      .then(data => {
        console.log(data);
      })
      .catch(reason => {
        console.error(
          `The jupyter_notebook_intelligence server extension appears to be missing.\n${reason}`
        );
      });

    requestAPI<any>('inline-completions', {method: 'POST', body: '{}'})
      .then(data => {
        console.log(data);
      })
      .catch(reason => {
        console.error(
          `The jupyter_notebook_intelligence server extension appears to be missing.\n${reason}`
        );
      });

    const getGitHubAuthStatus = () => {
      requestAPI<any>('gh-auth-status')
      .then(data => {
        if (!data.authenticated) {
          console.log(`Login to GitHub Copilot using ${data.verification_uri} and device code ${data.user_code}`);
        }
      })
      .catch(reason => {
        console.error(
          `The jupyter_notebook_intelligence server extension appears to be missing.\n${reason}`
        );
      });
    };

    setInterval(() => {
      getGitHubAuthStatus();
    }, 30000);

    getGitHubAuthStatus();
  }
};

export default plugin;
