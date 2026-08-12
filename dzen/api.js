// Yandex Dzen API Module
const https = require('https');

class DzenApi {
    constructor(accessToken) {
        this.accessToken = accessToken;
        this.baseUrl = 'https://api.dzen.ru';
    }

    async call(endpoint, params = {}) {
        const headers = {
            'Authorization': `Bearer ${this.accessToken}`,
            'Content-Type': 'application/json'
        };

        return new Promise((resolve, reject) => {
            const url = new URL(`${this.baseUrl}${endpoint}`);
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

    async getChannelInfo(channelId) {
        return this.call(`/v1/channels/${channelId}`);
    }

    async getPosts(channelId, limit = 10) {
        return this.call(`/v1/channels/${channelId}/posts`, { limit });
    }

    async createPost(channelId, title, content) {
        return this.call(`/v1/channels/${channelId}/posts`, {
            method: 'POST',
            body: JSON.stringify({ title, content })
        });
    }
}

module.exports = DzenApi;
