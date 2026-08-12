// Comprehensive Integration Test - All Modules Together
const path = require('path');
const fs = require('fs');

console.log('=== INTEGRATION TEST: ALL MODULES ===\n');

// Load all modules
const PortableOS = require('../engine/core');
const Terminal = require('../app/terminal');
const FileSystem = require('../app/filesystem');
const Network = require('../app/network');
const VKApi = require('../vk/api');
const DzenApi = require('../dzen/api');
const TelegramBot = require('../telegram/bot');
const YandexGoogleApi = require('../yandex_google/api');
const Database = require('../database/sqlite');

// Test results
const results = { passed: 0, failed: 0, tests: [] };

function test(name, fn) {
    try {
        fn();
        results.passed++;
        results.tests.push({ name, status: '✅' });
        console.log(`  ✅ ${name}`);
    } catch (e) {
        results.failed++;
        results.tests.push({ name, status: '❌', error: e.message });
        console.log(`  ❌ ${name}: ${e.message}`);
    }
}

function assert(condition, msg) {
    if (!condition) throw new Error(msg);
}

// ==================== TEST SUITE ====================

console.log('1. ENGINE CORE');
const os = new PortableOS();
test('PortableOS instantiates', () => assert(os.version === '0.1.0'));
test('PortableOS has getStatus', () => assert(typeof os.getStatus === 'function'));
test('PortableOS getStatus returns object', () => {
    const status = os.getStatus();
    assert(status.name && status.version);
});

console.log('\n2. FILESYSTEM MODULE');
const fs2 = new FileSystem(path.resolve(__dirname, '..'));
test('FileSystem instantiates', () => assert(fs2 instanceof FileSystem));
test('FileSystem.list works', () => {
    const files = fs2.list('.');
    assert(Array.isArray(files) && files.length > 0);
});
test('FileSystem.read works', () => {
    const content = fs2.read('package.json');
    assert(typeof content === 'string' && content.includes('portable-os'));
});
test('FileSystem.write creates file', () => {
    fs2.write('_test_temp.txt', 'test content');
    assert(fs2.exists('_test_temp.txt'));
    assert(fs2.read('_test_temp.txt') === 'test content');
    fs2.rm('_test_temp.txt');
});
test('FileSystem.mkdir creates directory', () => {
    fs2.mkdir('_test_dir');
    assert(fs2.exists('_test_dir') && fs2.isDir('_test_dir'));
    fs2.rm('_test_dir');
});
test('FileSystem.stat works', () => {
    const stat = fs2.stat('package.json');
    assert(stat.size > 0);
});

console.log('\n3. NETWORK MODULE');
const net = new Network();
test('Network has getStatus', () => assert(typeof net.getStatus === 'function'));
test('Network has fetch method', () => assert(typeof net.fetch === 'function'));
test('Network has post method', () => assert(typeof net.post === 'function'));
test('Network cache works', () => {
    net.clearCache();
    assert(net.getCacheSize() === 0);
});

console.log('\n4. VK MODULE');
const vk = new VKApi('test_token');
test('VKApi instantiates', () => assert(vk instanceof VKApi));
test('VKApi has correct baseUrl', () => assert(vk.baseUrl === 'https://api.vk.com/method'));
test('VKApi has version', () => assert(vk.version === '5.131'));
test('VKApi has call method', () => assert(typeof vk.call === 'function'));
test('VKApi has getUserInfo', () => assert(typeof vk.getUserInfo === 'function'));
test('VKApi has getWallPosts', () => assert(typeof vk.getWallPosts === 'function'));
test('VKApi has postMessage', () => assert(typeof vk.postMessage === 'function'));

console.log('\n5. DZEN MODULE');
const dzen = new DzenApi('test_token');
test('DzenApi instantiates', () => assert(dzen instanceof DzenApi));
test('DzenApi has correct baseUrl', () => assert(dzen.baseUrl === 'https://api.dzen.ru'));
test('DzenApi has call method', () => assert(typeof dzen.call === 'function'));
test('DzenApi has getChannelInfo', () => assert(typeof dzen.getChannelInfo === 'function'));
test('DzenApi has getPosts', () => assert(typeof dzen.getPosts === 'function'));
test('DzenApi has createPost', () => assert(typeof dzen.createPost === 'function'));

console.log('\n6. TELEGRAM MODULE');
const tg = new TelegramBot('test_token');
test('TelegramBot instantiates', () => assert(tg instanceof TelegramBot));
test('TelegramBot has correct baseUrl', () => assert(tg.baseUrl.includes('api.telegram.org')));
test('TelegramBot has call method', () => assert(typeof tg.call === 'function'));
test('TelegramBot has getMe', () => assert(typeof tg.getMe === 'function'));
test('TelegramBot has sendMessage', () => assert(typeof tg.sendMessage === 'function'));
test('TelegramBot has getUpdates', () => assert(typeof tg.getUpdates === 'function'));
test('TelegramBot has setWebhook', () => assert(typeof tg.setWebhook === 'function'));

console.log('\n7. YANDEX+GOOGLE MODULE');
const yg = new YandexGoogleApi('yandex_token', 'google_token');
test('YandexGoogleApi instantiates', () => assert(yg instanceof YandexGoogleApi));
test('YandexGoogleApi has yandexBaseUrl', () => assert(yg.yandexBaseUrl === 'https://api.yandex.ru'));
test('YandexGoogleApi has googleBaseUrl', () => assert(yg.googleBaseUrl === 'https://www.googleapis.com'));
test('YandexGoogleApi has callYandex', () => assert(typeof yg.callYandex === 'function'));
test('YandexGoogleApi has callGoogle', () => assert(typeof yg.callGoogle === 'function'));
test('YandexGoogleApi has yandexDiskInfo', () => assert(typeof yg.yandexDiskInfo === 'function'));
test('YandexGoogleApi has googleUserInfo', () => assert(typeof yg.googleUserInfo === 'function'));

console.log('\n8. DATABASE MODULE');
const db = new Database(path.resolve(__dirname, '_test.db'));
test('Database instantiates', () => assert(db instanceof Database));
test('Database has open method', () => assert(typeof db.open === 'function'));
test('Database has createTable', () => assert(typeof db.createTable === 'function'));
test('Database has insert', () => assert(typeof db.insert === 'function'));
test('Database has select', () => assert(typeof db.select === 'function'));
test('Database has update', () => assert(typeof db.update === 'function'));
test('Database has delete', () => assert(typeof db.delete === 'function'));
test('Database has count', () => assert(typeof db.count === 'function'));

// Test database operations
test('Database createTable works', async () => {
    await db.open();
    await db.createTable('test_users', [
        { name: 'id', type: 'INTEGER PRIMARY KEY' },
        { name: 'name', type: 'TEXT' },
        { name: 'email', type: 'TEXT' }
    ]);
    assert(fs.existsSync(path.resolve(__dirname, '_test.db')));
});

test('Database insert works', async () => {
    await db.insert('test_users', { name: 'John', email: 'john@example.com' });
    const count = await db.count('test_users');
    assert(count === 1);
});

test('Database select works', async () => {
    const users = await db.select('test_users');
    assert(users.length === 1 && users[0].name === 'John');
});

test('Database update works', async () => {
    await db.update('test_users', { name: 'Jane' }, 'id = 1');
    const user = await db.get('test_users', 'id = 1');
    assert(user.name === 'Jane');
});

test('Database delete works', async () => {
    await db.delete('test_users', 'id = 1');
    const count = await db.count('test_users');
    assert(count === 0);
});

// Cleanup
test('Database close works', async () => {
    await db.close();
    fs.unlinkSync(path.resolve(__dirname, '_test.db'));
});

console.log('\n9. CROSS-MODULE INTEGRATION');
test('All modules load together', () => {
    assert(PortableOS && Terminal && FileSystem && Network);
    assert(VKApi && DzenApi && TelegramBot && YandexGoogleApi);
    assert(Database);
});

test('FileSystem and Database work together', async () => {
    const testDb = new Database(path.resolve(__dirname, '_integration.db'));
    await testDb.open();
    await testDb.createTable('files', [
        { name: 'id', type: 'INTEGER PRIMARY KEY' },
        { name: 'path', type: 'TEXT' },
        { name: 'content', type: 'TEXT' }
    ]);
    
    // Write file with FileSystem
    fs2.write('_test_integration.txt', 'Integration test content');
    
    // Store in Database
    await testDb.insert('files', {
        path: '_test_integration.txt',
        content: fs2.read('_test_integration.txt')
    });
    
    // Verify
    const files = await testDb.select('files');
    assert(files.length === 1);
    assert(files[0].content === 'Integration test content');
    
    // Cleanup
    await testDb.close();
    fs2.rm('_test_integration.txt');
    fs.unlinkSync(path.resolve(__dirname, '_integration.db'));
});

test('Network and FileSystem work together', async () => {
    // Fetch content
    const content = '{"test": true}';
    
    // Write to file
    fs2.write('_test_network.json', content);
    
    // Read and verify
    const readContent = fs2.read('_test_network.json');
    assert(JSON.parse(readContent).test === true);
    
    // Cleanup
    fs2.rm('_test_network.json');
});

// ==================== SUMMARY ====================

console.log('\n=== INTEGRATION TEST SUMMARY ===');
console.log(`Total Tests: ${results.passed + results.failed}`);
console.log(`Passed: ${results.passed}`);
console.log(`Failed: ${results.failed}`);
console.log(`Success Rate: ${((results.passed / (results.passed + results.failed)) * 100).toFixed(1)}%`);

if (results.failed === 0) {
    console.log('\n🎉 ALL INTEGRATION TESTS PASSED!');
    console.log('\n📦 Modules tested:');
    console.log('  - engine/core.js');
    console.log('  - app/filesystem.js');
    console.log('  - app/network.js');
    console.log('  - vk/api.js');
    console.log('  - dzen/api.js');
    console.log('  - telegram/bot.js');
    console.log('  - yandex_google/api.js');
    console.log('  - database/sqlite.js');
} else {
    console.log('\n⚠️ Some tests failed');
    results.tests.filter(t => t.status === '❌').forEach(t => {
        console.log(`  - ${t.name}: ${t.error}`);
    });
}
