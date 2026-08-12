// Portable OS Filesystem
const fs = require('fs');
const path = require('path');

class FileSystem {
  constructor(rootPath) {
    this.rootPath = rootPath || process.cwd();
  }

  list(dirPath = '.') {
    const fullPath = path.resolve(this.rootPath, dirPath);
    return fs.readdirSync(fullPath);
  }

  read(filePath) {
    const fullPath = path.resolve(this.rootPath, filePath);
    return fs.readFileSync(fullPath, 'utf8');
  }

  write(filePath, content) {
    const fullPath = path.resolve(this.rootPath, filePath);
    fs.writeFileSync(fullPath, content, 'utf8');
  }

  exists(filePath) {
    const fullPath = path.resolve(this.rootPath, filePath);
    return fs.existsSync(fullPath);
  }

  isDir(filePath) {
    const fullPath = path.resolve(this.rootPath, filePath);
    return fs.statSync(fullPath).isDirectory();
  }
}

module.exports = new FileSystem();
