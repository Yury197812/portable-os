// Portable OS Network
const https = require('https');
const http = require('http');

class Network {
  constructor() {
    this.connected = false;
  }

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

  async fetch(url) {
    return new Promise((resolve, reject) => {
      const client = url.startsWith('https') ? https : http;
      client.get(url, (res) => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', () => resolve(data));
      }).on('error', reject);
    });
  }

  getStatus() {
    return { connected: this.connected };
  }
}

module.exports = new Network();
