// All Modules Comprehensive Test
const path = require('path');
const fs = require('fs');

console.log('=== COMPREHENSIVE MODULE TEST ===\n');

// Test results tracking
const results = {
    passed: 0,
    failed: 0,
    modules: []
};

function testModule(name, testFn) {
    try {
        testFn();
        results.passed++;
        results.modules.push({ name, status: '✅ PASS' });
        console.log(`✅ ${name}`);
    } catch (e) {
        results.failed++;
        results.modules.push({ name, status: '❌ FAIL', error: e.message });
        console.log(`❌ ${name}: ${e.message}`);
    }
}

// 1. Engine Core
console.log('1. ENGINE CORE');
testModule('engine/core.js loads', () => {
    const PortableOS = require('../engine/core');
    assert(typeof PortableOS === 'function', 'PortableOS should be a class');
});

testModule('engine/core.js instantiates', () => {
    const PortableOS = require('../engine/core');
    const os = new PortableOS();
    assert(os.version === '0.1.0', 'Version should be 0.1.0');
});

// 2. App Modules
console.log('\n2. APP MODULES');
testModule('app/terminal.js loads', () => {
    const Terminal = require('../app/terminal');
    assert(Terminal, 'Terminal should exist');
});

testModule('app/filesystem.js loads', () => {
    const FileSystem = require('../app/filesystem');
    assert(FileSystem, 'FileSystem should exist');
});

testModule('app/network.js loads', () => {
    const Network = require('../app/network');
    assert(Network, 'Network should exist');
});

// 3. Platform Modules
console.log('\n3. PLATFORM MODULES');
testModule('vk/api.js loads', () => {
    const VKApi = require('../vk/api');
    const vk = new VKApi('test');
    assert(vk.baseUrl === 'https://api.vk.com/method', 'VK baseUrl correct');
});

testModule('dzen/api.js loads', () => {
    const DzenApi = require('../dzen/api');
    const dzen = new DzenApi('test');
    assert(dzen.baseUrl === 'https://api.dzen.ru', 'Dzen baseUrl correct');
});

testModule('telegram/bot.js loads', () => {
    const TelegramBot = require('../telegram/bot');
    const tg = new TelegramBot('test');
    assert(tg.baseUrl.includes('api.telegram.org'), 'Telegram baseUrl correct');
});

testModule('yandex_google/api.js loads', () => {
    const YandexGoogleApi = require('../yandex_google/api');
    const yg = new YandexGoogleApi('yandex', 'google');
    assert(yg.yandexBaseUrl === 'https://api.yandex.ru', 'Yandex baseUrl correct');
    assert(yg.googleBaseUrl === 'https://www.googleapis.com', 'Google baseUrl correct');
});

// 4. Database Module
console.log('\n4. DATABASE MODULE');
testModule('database/sqlite.js loads', () => {
    const Database = require('../database/sqlite');
    assert(Database, 'Database should exist');
});

testModule('database/sqlite.js instantiates', () => {
    const Database = require('../database/sqlite');
    const db = new Database('test.db');
    assert(db.dbPath.includes('test.db'), 'Database path correct');
});

// 5. Integration Test
console.log('\n5. INTEGRATION TEST');
testModule('All modules can be required together', () => {
    const PortableOS = require('../engine/core');
    const Terminal = require('../app/terminal');
    const FileSystem = require('../app/filesystem');
    const Network = require('../app/network');
    const VKApi = require('../vk/api');
    const DzenApi = require('../dzen/api');
    const TelegramBot = require('../telegram/bot');
    const YandexGoogleApi = require('../yandex_google/api');
    const Database = require('../database/sqlite');
    
    assert(PortableOS && Terminal && FileSystem && Network, 'Core modules loaded');
    assert(VKApi && DzenApi && TelegramBot && YandexGoogleApi, 'Platform modules loaded');
    assert(Database, 'Database module loaded');
});

// Summary
console.log('\n=== TEST SUMMARY ===');
console.log(`Total: ${results.passed + results.failed}`);
console.log(`Passed: ${results.passed}`);
console.log(`Failed: ${results.failed}`);
console.log(`Success Rate: ${((results.passed / (results.passed + results.failed)) * 100).toFixed(1)}%`);

if (results.failed === 0) {
    console.log('\n🎉 ALL TESTS PASSED!');
} else {
    console.log('\n⚠️ Some tests failed');
    results.modules.filter(m => m.status.includes('FAIL')).forEach(m => {
        console.log(`  - ${m.name}: ${m.error}`);
    });
}

// Helper function
function assert(condition, message) {
    if (!condition) throw new Error(message);
}
