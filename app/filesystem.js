// Portable OS Filesystem - Enhanced
const fs = require('fs');
const path = require('path');

class FileSystem {
    constructor(rootPath) {
        this.rootPath = rootPath || process.cwd();
        this.watchers = new Map();
    }

    // Basic operations
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
        const dir = path.dirname(fullPath);
        if (!fs.existsSync(dir)) {
            fs.mkdirSync(dir, { recursive: true });
        }
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

    // Advanced operations
    mkdir(dirPath) {
        const fullPath = path.resolve(this.rootPath, dirPath);
        fs.mkdirSync(fullPath, { recursive: true });
    }

    rm(filePath) {
        const fullPath = path.resolve(this.rootPath, filePath);
        fs.rmSync(fullPath, { recursive: true, force: true });
    }

    cp(src, dest) {
        const srcPath = path.resolve(this.rootPath, src);
        const destPath = path.resolve(this.rootPath, dest);
        fs.cpSync(srcPath, destPath, { recursive: true });
    }

    mv(src, dest) {
        const srcPath = path.resolve(this.rootPath, src);
        const destPath = path.resolve(this.rootPath, dest);
        fs.renameSync(srcPath, destPath);
    }

    stat(filePath) {
        const fullPath = path.resolve(this.rootPath, filePath);
        return fs.statSync(fullPath);
    }

    size(filePath) {
        return this.stat(filePath).size;
    }

    // Watch operations
    watch(dirPath, callback) {
        const fullPath = path.resolve(this.rootPath, dirPath);
        const watcher = fs.watch(fullPath, (event, filename) => {
            callback(event, filename);
        });
        this.watchers.set(dirPath, watcher);
        return watcher;
    }

    unwatch(dirPath) {
        const watcher = this.watchers.get(dirPath);
        if (watcher) {
            watcher.close();
            this.watchers.delete(dirPath);
        }
    }

    // Path utilities
    resolve(filePath) {
        return path.resolve(this.rootPath, filePath);
    }

    join(...segments) {
        return path.join(this.rootPath, ...segments);
    }

    relative(filePath) {
        const fullPath = path.resolve(this.rootPath, filePath);
        return path.relative(this.rootPath, fullPath);
    }
}

module.exports = FileSystem;
