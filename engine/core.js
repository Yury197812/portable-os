// Portable OS Engine Core
const fs = require('fs');
const path = require('path');
const os = require('os');

class PortableOS {
  constructor() {
    this.version = '0.1.0';
    this.name = 'Portable OS';
    this.components = {};
  }

  async init() {
    console.log(`Initializing ${this.name} v${this.version}...`);
    this.loadComponents();
    console.log('System ready.');
  }

  loadComponents() {
    this.components.terminal = require('../app/terminal');
    this.components.fileSystem = require('../app/filesystem');
    this.components.network = require('../app/network');
  }

  getStatus() {
    return {
      name: this.name,
      version: this.version,
      uptime: process.uptime(),
      memory: process.memoryUsage(),
      components: Object.keys(this.components)
    };
  }
}

module.exports = PortableOS;

if (require.main === module) {
  const os = new PortableOS();
  os.init();
}
