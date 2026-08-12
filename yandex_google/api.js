// Yandex + Google API Module
const https = require('https');

class YandexGoogleApi {
    constructor(yandexToken, googleToken) {
        this.yandexToken = yandexToken;
        this.googleToken = googleToken;
        this.yandexBaseUrl = 'https://api.yandex.ru';
        this.googleBaseUrl = 'https://www.googleapis.com';
    }

    async callYandex(endpoint, params = {}) {
        const headers = {
            'Authorization': `OAuth ${this.yandexToken}`,
            'Content-Type': 'application/json'
        };

        return new Promise((resolve, reject) => {
            const url = new URL(`${this.yandexBaseUrl}${endpoint}`);
            Object.entries(params).forEach(([key, value]) => {
                url.searchParams.append(key, value);
            });

            https.get(url, { headers }, (res) => {
                let data = '';
                res.on('data', chunk => data += chunk);
                res.on('end', () => {
                    try {
                        const json = JSON.parse(data);
                        resolve(json);
                    } catch (e) {
                        reject(e);
                    }
                });
            }).on('error', reject);
        });
    }

    async callGoogle(endpoint, params = {}) {
        const headers = {
            'Authorization': `Bearer ${this.googleToken}`,
            'Content-Type': 'application/json'
        };

        return new Promise((resolve, reject) => {
            const url = new URL(`${this.googleBaseUrl}${endpoint}`);
            Object.entries(params).forEach(([key, value]) => {
                url.searchParams.append(key, value);
            });

            https.get(url, { headers }, (res) => {
                let data = '';
                res.on('data', chunk => data += chunk);
                res.on('end', () => {
                    try {
                        const json = JSON.parse(data);
                        resolve(json);
                    } catch (e) {
                        reject(e);
                    }
                });
            }).on('error', reject);
        });
    }

    // Yandex methods
    async yandexDiskInfo() {
        return this.callYandex('/v1/disk');
    }

    async yandexDiskFiles(path = '/') {
        return this.callYandex('/v1/disk/resources', { path });
    }

    // Google methods
    async googleUserInfo() {
        return this.callGoogle('/oauth2/v3/userinfo');
    }

    async googleDriveFiles() {
        return this.callGoogle('/drive/v3/files');
    }
}

module.exports = YandexGoogleApi;
