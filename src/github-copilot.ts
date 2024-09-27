import { requestAPI } from "./handler";

const LOGIN_STATUS_UPDATE_INTERVAL = 3000;

export enum GitHubCopilotLoginStatus {
    NotLoggedIn = 'NOT_LOGGED_IN',
    ActivatingDevice = 'ACTIVATING_DEVICE',
    LoggingIn = 'LOGGING_IN',
    LoggedIn = 'LOGGED_IN'
}

export class GitHubCopilot {
    static _loginStatus = GitHubCopilotLoginStatus.NotLoggedIn;

    static initialize() {
        setInterval(() => {
            this.updateGitHubLoginStatus();
          }, LOGIN_STATUS_UPDATE_INTERVAL);
    }

    static getLoginStatus(): GitHubCopilotLoginStatus {
        return this._loginStatus;
    }

    static async loginToGitHub() {
        return new Promise((resolve, reject) => {
            requestAPI<any>('gh-login', {method: 'POST'})
            .then(data => {
                resolve({
                    verificationURI: data.verification_uri,
                    userCode: data.user_code
                });
                this.updateGitHubLoginStatus();
                console.log(`Login to GitHub Copilot using ${data.verification_uri} and device code ${data.user_code}`);
            })
            .catch(reason => {
                console.error(
                `The jupyter_notebook_intelligence server extension appears to be missing.\n${reason}`
                );
                reject(reason);
            });
        });
      
    }

    static updateGitHubLoginStatus() {
        requestAPI<any>('gh-login-status')
        .then(response => {
            this._loginStatus = response.status;
        })
        .catch(reason => {
          console.error(
            `The jupyter_notebook_intelligence server extension appears to be missing.\n${reason}`
          );
        });
    }

    static async chatRequest(prompt: string) {
        return requestAPI<any>('chat', { method: 'POST', body: JSON.stringify({"prompt": prompt})});
    }

    static async inlineCompletionsRequest(prefix: string, suffix: string, language: string) {
        return requestAPI<any>('inline-completions', {
            method: 'POST',
            body: JSON.stringify({
              prefix,
              suffix,
              language
            })}
          );
    }

}
