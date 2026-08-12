// Platform Modules Tests
const VKApi = require('../vk/api');
const DzenApi = require('../dzen/api');
const TelegramBot = require('../telegram/bot');
const YandexGoogleApi = require('../yandex_google/api');

console.log('Testing Platform Modules...\n');

// Test VK Module
console.log('1. VK Module');
const vk = new VKApi('test_token');
console.log('   ✓ VKApi loaded');
console.log('   ✓ baseUrl:', vk.baseUrl);
console.log('   ✓ version:', vk.version);

// Test Dzen Module
console.log('2. Dzen Module');
const dzen = new DzenApi('test_token');
console.log('   ✓ DzenApi loaded');
console.log('   ✓ baseUrl:', dzen.baseUrl);

// Test Telegram Module
console.log('3. Telegram Module');
const tg = new TelegramBot('test_token');
console.log('   ✓ TelegramBot loaded');
console.log('   ✓ baseUrl:', tg.baseUrl);

// Test Yandex+Google Module
console.log('4. Yandex+Google Module');
const yg = new YandexGoogleApi('yandex_token', 'google_token');
console.log('   ✓ YandexGoogleApi loaded');
console.log('   ✓ yandexBaseUrl:', yg.yandexBaseUrl);
console.log('   ✓ googleBaseUrl:', yg.googleBaseUrl);

console.log('\nAll platform modules loaded successfully!');
