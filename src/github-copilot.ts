// Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

import { requestAPI } from "./handler";

const LOGIN_STATUS_UPDATE_INTERVAL = 3000;

export enum GitHubCopilotLoginStatus {
    NotLoggedIn = 'NOT_LOGGED_IN',
    ActivatingDevice = 'ACTIVATING_DEVICE',
    LoggingIn = 'LOGGING_IN',
    LoggedIn = 'LOGGED_IN'
}

export interface IDeviceVerificationInfo {
    verificationURI: string;
    userCode: string;
}

export class GitHubCopilot {
    static _loginStatus = GitHubCopilotLoginStatus.NotLoggedIn;
    static _deviceVerificationInfo: IDeviceVerificationInfo = {
        verificationURI: '',
        userCode: ''
    };

    static initialize() {
        this.updateGitHubLoginStatus();

        setInterval(() => {
            this.updateGitHubLoginStatus();
        }, LOGIN_STATUS_UPDATE_INTERVAL);
    }

    static getLoginStatus(): GitHubCopilotLoginStatus {
        return this._loginStatus;
    }

    static getDeviceVerificationInfo(): IDeviceVerificationInfo {
        return this._deviceVerificationInfo;
    }

    static async loginToGitHub() {
        this._loginStatus = GitHubCopilotLoginStatus.ActivatingDevice;
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
            this._deviceVerificationInfo.verificationURI = response.verification_uri || '';
            this._deviceVerificationInfo.userCode = response.user_code || '';
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

    static async explainThisRequest(code: string) {
        return requestAPI<any>('explain-this', { method: 'POST', body: JSON.stringify({"selection": code})});
    }

    static async fixThisRequest(code: string) {
        return requestAPI<any>('fix-this', { method: 'POST', body: JSON.stringify({"selection": code})});
    }
}
