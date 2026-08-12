// Portable OS Network - Enhanced
const https = require('https');
const http = require('http');
const url = require('url');

class Network {
    constructor() {
        this.connected = false;
        this.cache = new Map();
        this.cacheTimeout = 5 * 60 * 1000; // 5 minutes
    }

    // Basic operations
    async checkConnection() {
        return new Promise((resolve) => {
            https.get('https://github.com', (res) => {
                this.connected = res.statusCode === 200;
                resolve(this.connected);
            }).on('error', () => {
                this.connected = false;
                resolve(false);
            });
        });
    }

    async fetch(urlString, options = {}) {
        const { useCache = true, timeout = 30000 } = options;
        
        // Check cache
        if (useCache && this.cache.has(urlString)) {
            const cached = this.cache.get(urlString);
            if (Date.now() - cached.timestamp < this.cacheTimeout) {
                return cached.data;
            }
        }

        return new Promise((resolve, reject) => {
            const parsedUrl = new URL(urlString);
            const client = parsedUrl.protocol === 'https:' ? https : http;
            
            const req = client.get(urlString, { timeout }, (res) => {
                let data = '';
                res.on('data', chunk => data += chunk);
                res.on('end', () => {
                    // Cache the result
                    if (useCache) {
                        this.cache.set(urlString, {
                            data,
                            timestamp: Date.now()
                        });
                    }
                    resolve(data);
                });
            });
            
            req.on('error', reject);
            req.on('timeout', () => {
                req.destroy();
                reject(new Error('Request timeout'));
            });
        });
    }

    async post(urlString, data, options = {}) {
        const { timeout = 30000 } = options;
        
        return new Promise((resolve, reject) => {
            const parsedUrl = new URL(urlString);
            const client = parsedUrl.protocol === 'https:' ? https : http;
            
            const postData = JSON.stringify(data);
            
            const req = client.request(urlString, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Content-Length': Buffer.byteLength(postData)
                },
                timeout
            }, (res) => {
                let responseData = '';
                res.on('data', chunk => responseData += chunk);
                res.on('end', () => resolve(responseData));
            });
            
            req.on('error', reject);
            req.on('timeout', () => {
                req.destroy();
                reject(new Error('Request timeout'));
            });
            
            req.write(postData);
            req.end();
        });
    }

    // Cache operations
    clearCache() {
        this.cache.clear();
    }

    getCacheSize() {
        return this.cache.size;
    }

    // Status
    getStatus() {
        return {
            connected: this.connected,
            cacheSize: this.cache.size
        };
    }
}

module.exports = Network;
