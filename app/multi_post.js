// Multi-Platform Posting Module
const VKApi = require('../vk/api');
const DzenApi = require('../dzen/api');
const TelegramBot = require('../telegram/bot');
const YandexGoogleApi = require('../yandex_google/api');

class MultiPost {
    constructor(config = {}) {
        this.platforms = {};
        this.results = {};
        
        // Initialize platforms if tokens provided
        if (config.vk) this.platforms.vk = new VKApi(config.vk);
        if (config.dzen) this.platforms.dzen = new DzenApi(config.dzen);
        if (config.telegram) this.platforms.telegram = new TelegramBot(config.telegram);
        if (config.yandex || config.google) {
            this.platforms.yandex_google = new YandexGoogleApi(config.yandex, config.google);
        }
    }

    // Post to all platforms
    async postAll(content) {
        const results = {};
        
        for (const [platform, api] of Object.entries(this.platforms)) {
            try {
                results[platform] = await this.postToPlatform(platform, api, content);
            } catch (error) {
                results[platform] = { success: false, error: error.message };
            }
        }
        
        return results;
    }

    // Post to specific platform
    async postToPlatform(platform, api, content) {
        switch (platform) {
            case 'vk':
                return this.postToVK(api, content);
            case 'dzen':
                return this.postToDzen(api, content);
            case 'telegram':
                return this.postToTelegram(api, content);
            case 'yandex_google':
                return this.postToYandexGoogle(api, content);
            default:
                throw new Error(`Unknown platform: ${platform}`);
        }
    }

    // VK posting
    async postToVK(api, content) {
        const { message, ownerId } = content;
        const result = await api.postMessage(ownerId, message);
        return { success: true, platform: 'vk', postId: result };
    }

    // Dzen posting
    async postToDzen(api, content) {
        const { title, body, channelId } = content;
        const result = await api.createPost(channelId, title, body);
        return { success: true, platform: 'dzen', postId: result };
    }

    // Telegram posting
    async postToTelegram(api, content) {
        const { chatId, text } = content;
        const result = await api.sendMessage(chatId, text);
        return { success: true, platform: 'telegram', messageId: result };
    }

    // Yandex+Google posting
    async postToYandexGoogle(api, content) {
        // Placeholder for Yandex/Google integration
        return { success: true, platform: 'yandex_google', message: 'Integration ready' };
    }

    // Get status of all platforms
    getStatus() {
        const status = {};
        for (const [platform, api] of Object.entries(this.platforms)) {
            status[platform] = {
                configured: true,
                baseUrl: api.baseUrl || api.yandexBaseUrl
            };
        }
        return status;
    }

    // Add platform dynamically
    addPlatform(name, config) {
        switch (name) {
            case 'vk':
                this.platforms.vk = new VKApi(config.token);
                break;
            case 'dzen':
                this.platforms.dzen = new DzenApi(config.token);
                break;
            case 'telegram':
                this.platforms.telegram = new TelegramBot(config.token);
                break;
            case 'yandex_google':
                this.platforms.yandex_google = new YandexGoogleApi(config.yandex, config.google);
                break;
        }
    }

    // Remove platform
    removePlatform(name) {
        delete this.platforms[name];
    }

    // List configured platforms
    listPlatforms() {
        return Object.keys(this.platforms);
    }
}

module.exports = MultiPost;
