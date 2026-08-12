// Portable OS Tests
const assert = require('assert');
const FileSystem = require('../app/filesystem');
const Network = require('../app/network');

console.log('Running tests...\n');

// Test FileSystem
console.log('1. FileSystem module');
assert.ok(FileSystem, 'FileSystem loaded');
console.log('   ✓ FileSystem loaded');

// Test Network
console.log('2. Network module');
assert.ok(Network, 'Network loaded');
console.log('   ✓ Network loaded');

// Test Terminal
console.log('3. Terminal module');
const Terminal = require('../app/terminal');
assert.ok(Terminal, 'Terminal loaded');
console.log('   ✓ Terminal loaded');

console.log('\nAll tests passed!');
