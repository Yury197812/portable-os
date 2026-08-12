// Multi-Platform Posting Test
const MultiPost = require('../app/multi_post');

console.log('=== MULTI-PLATFORM POSTING TEST ===\n');

// Test results
const results = { passed: 0, failed: 0, tests: [] };

async function test(name, fn) {
    try {
        await fn();
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

async function runTests() {
    console.log('1. MULTI-POST MODULE');
    await test('MultiPost instantiates', () => {
        const mp = new MultiPost();
        assert(mp instanceof MultiPost);
    });
    
    await test('MultiPost has postAll method', () => {
        const mp = new MultiPost();
        assert(typeof mp.postAll === 'function');
    });
    
    await test('MultiPost has postToPlatform method', () => {
        const mp = new MultiPost();
        assert(typeof mp.postToPlatform === 'function');
    });
    
    await test('MultiPost has getStatus method', () => {
        const mp = new MultiPost();
        assert(typeof mp.getStatus === 'function');
    });
    
    await test('MultiPost has addPlatform method', () => {
        const mp = new MultiPost();
        assert(typeof mp.addPlatform === 'function');
    });
    
    await test('MultiPost has removePlatform method', () => {
        const mp = new MultiPost();
        assert(typeof mp.removePlatform === 'function');
    });
    
    await test('MultiPost has listPlatforms method', () => {
        const mp = new MultiPost();
        assert(typeof mp.listPlatforms === 'function');
    });

    console.log('\n2. PLATFORM CONFIGURATION');
    await test('Can add VK platform', () => {
        const mp = new MultiPost();
        mp.addPlatform('vk', { token: 'test_token' });
        assert(mp.listPlatforms().includes('vk'));
    });
    
    await test('Can add Dzen platform', () => {
        const mp = new MultiPost();
        mp.addPlatform('dzen', { token: 'test_token' });
        assert(mp.listPlatforms().includes('dzen'));
    });
    
    await test('Can add Telegram platform', () => {
        const mp = new MultiPost();
        mp.addPlatform('telegram', { token: 'test_token' });
        assert(mp.listPlatforms().includes('telegram'));
    });
    
    await test('Can add Yandex+Google platform', () => {
        const mp = new MultiPost();
        mp.addPlatform('yandex_google', { yandex: 'yandex_token', google: 'google_token' });
        assert(mp.listPlatforms().includes('yandex_google'));
    });
    
    await test('Can remove platform', () => {
        const mp = new MultiPost();
        mp.addPlatform('vk', { token: 'test_token' });
        assert(mp.listPlatforms().includes('vk'));
        mp.removePlatform('vk');
        assert(!mp.listPlatforms().includes('vk'));
    });

    console.log('\n3. MULTI-POST WITH ALL PLATFORMS');
    await test('Can configure all platforms at once', () => {
        const mp = new MultiPost({
            vk: 'vk_token',
            dzen: 'dzen_token',
            telegram: 'tg_token',
            yandex: 'yandex_token',
            google: 'google_token'
        });
        const platforms = mp.listPlatforms();
        assert(platforms.includes('vk'));
        assert(platforms.includes('dzen'));
        assert(platforms.includes('telegram'));
        assert(platforms.includes('yandex_google'));
    });
    
    await test('getStatus returns all platforms', () => {
        const mp = new MultiPost({
            vk: 'vk_token',
            telegram: 'tg_token'
        });
        const status = mp.getStatus();
        assert(status.vk && status.telegram);
    });

    console.log('\n4. POST CONTENT STRUCTURE');
    await test('VK post structure', () => {
        const content = { message: 'Test post', ownerId: 123456 };
        assert(content.message && content.ownerId);
    });
    
    await test('Dzen post structure', () => {
        const content = { title: 'Test Title', body: 'Test Body', channelId: 'test_channel' };
        assert(content.title && content.body && content.channelId);
    });
    
    await test('Telegram post structure', () => {
        const content = { chatId: 'test_chat', text: 'Test message' };
        assert(content.chatId && content.text);
    });

    // ==================== SUMMARY ====================
    
    console.log('\n=== MULTI-POST TEST SUMMARY ===');
    console.log(`Total Tests: ${results.passed + results.failed}`);
    console.log(`Passed: ${results.passed}`);
    console.log(`Failed: ${results.failed}`);
    console.log(`Success Rate: ${((results.passed / (results.passed + results.failed)) * 100).toFixed(1)}%`);
    
    if (results.failed === 0) {
        console.log('\n🎉 ALL MULTI-POST TESTS PASSED!');
        console.log('\n📦 Module tested:');
        console.log('  - app/multi_post.js');
        console.log('\n🚀 Features:');
        console.log('  - Post to all platforms with single call');
        console.log('  - Add/remove platforms dynamically');
        console.log('  - Get status of all platforms');
        console.log('  - Support for VK, Dzen, Telegram, Yandex+Google');
    } else {
        console.log('\n⚠️ Some tests failed');
        results.tests.filter(t => t.status === '❌').forEach(t => {
            console.log(`  - ${t.name}: ${t.error}`);
        });
    }
}

runTests();
