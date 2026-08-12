// VK API Module
const https = require('https');

class VKApi {
    constructor(accessToken) {
        this.accessToken = accessToken;
        this.baseUrl = 'https://api.vk.com/method';
        this.version = '5.131';
    }

    async call(method, params = {}) {
        params.access_token = this.accessToken;
        params.v = this.version;
        
        const queryString = Object.entries(params)
            .map(([key, value]) => `${key}=${encodeURIComponent(value)}`)
            .join('&');
        
        return new Promise((resolve, reject) => {
            https.get(`${this.baseUrl}/${method}?${queryString}`, (res) => {
                let data = '';
                res.on('data', chunk => data += chunk);
                res.on('end', () => {
                    try {
                        const json = JSON.parse(data);
                        if (json.error) {
                            reject(new Error(json.error.error_msg));
                        } else {
                            resolve(json.response);
                        }
                    } catch (e) {
                        reject(e);
                    }
                });
            }).on('error', reject);
        });
    }

    async getUserInfo(userId) {
        return this.call('users.get', { user_ids: userId });
    }

    async getWallPosts(ownerId, count = 10) {
        return this.call('wall.get', { owner_id: ownerId, count });
    }

    async postMessage(userId, message) {
        return this.call('messages.send', { user_id: userId, message });
    }
}

module.exports = VKApi;
