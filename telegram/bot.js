// Telegram Bot API Module
const https = require('https');

class TelegramBot {
    constructor(token) {
        this.token = token;
        this.baseUrl = `https://api.telegram.org/bot${token}`;
    }

    async call(method, params = {}) {
        return new Promise((resolve, reject) => {
            const url = new URL(`${this.baseUrl}/${method}`);
            Object.entries(params).forEach(([key, value]) => {
                url.searchParams.append(key, value);
            });

            https.get(url, (res) => {
                let data = '';
                res.on('data', chunk => data += chunk);
                res.on('end', () => {
                    try {
                        const json = JSON.parse(data);
                        if (json.ok) {
                            resolve(json.result);
                        } else {
                            reject(new Error(json.description));
                        }
                    } catch (e) {
                        reject(e);
                    }
                });
            }).on('error', reject);
        });
    }

    async getMe() {
        return this.call('getMe');
    }

    async sendMessage(chatId, text) {
        return this.call('sendMessage', { chat_id: chatId, text });
    }

    async getUpdates(offset = 0) {
        return this.call('getUpdates', { offset });
    }

    async setWebhook(url) {
        return this.call('setWebhook', { url });
    }
}

module.exports = TelegramBot;
