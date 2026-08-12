// Multi-Platform Posting Example
const MultiPost = require('../app/multi_post');

// Example: Post to all platforms
async function postToAllPlatforms() {
    console.log('🚀 Multi-Platform Posting Example\n');
    
    // Initialize with tokens
    const multiPost = new MultiPost({
        vk: 'YOUR_VK_TOKEN',
        dzen: 'YOUR_DZEN_TOKEN',
        telegram: 'YOUR_TELEGRAM_BOT_TOKEN',
        yandex: 'YOUR_YANDEX_TOKEN',
        google: 'YOUR_GOOGLE_TOKEN'
    });
    
    // Check status
    console.log('📋 Platform Status:');
    console.log(multiPost.getStatus());
    console.log('');
    
    // Content to post
    const content = {
        // VK
        vk: {
            message: 'Hello from Portable OS! 🚀',
            ownerId: 123456
        },
        // Dzen
        dzen: {
            title: 'Portable OS Launch',
            body: 'We are excited to announce Portable OS!',
            channelId: 'your-channel-id'
        },
        // Telegram
        telegram: {
            chatId: '@your_channel',
            text: '🚀 Portable OS is now live!'
        }
    };
    
    // Post to all platforms
    console.log('📤 Posting to all platforms...');
    const results = await multiPost.postAll(content);
    
    console.log('\n📊 Results:');
    for (const [platform, result] of Object.entries(results)) {
        console.log(`  ${platform}: ${result.success ? '✅' : '❌'}`);
        if (result.error) {
            console.log(`    Error: ${result.error}`);
        }
    }
}

// Example: Dynamic platform management
async function dynamicPlatformExample() {
    console.log('\n🔧 Dynamic Platform Management Example\n');
    
    const multiPost = new MultiPost();
    
    // Add platforms dynamically
    multiPost.addPlatform('vk', { token: 'vk_token' });
    multiPost.addPlatform('telegram', { token: 'tg_token' });
    
    console.log('Platforms:', multiPost.listPlatforms());
    
    // Remove a platform
    multiPost.removePlatform('vk');
    console.log('After removal:', multiPost.listPlatforms());
}

// Run examples
if (require.main === module) {
    postToAllPlatforms()
        .then(() => dynamicPlatformExample())
        .catch(console.error);
}

module.exports = { postToAllPlatforms, dynamicPlatformExample };
