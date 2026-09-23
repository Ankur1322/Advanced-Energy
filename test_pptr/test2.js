const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({ args: ['--no-sandbox', '--disable-setuid-sandbox'] });
  const page = await browser.newPage();
  
  page.on('console', msg => console.log('PAGE LOG:', msg.text()));
  page.on('pageerror', error => console.log('PAGE ERROR:', error.message));

  try {
    await page.goto('http://localhost:3000', { waitUntil: 'domcontentloaded' });
    console.log("Page loaded");
    
    // Check if input is visible
    const inputVisible = await page.evaluate(() => {
      const el = document.querySelector('#chat-input');
      if (!el) return false;
      const rect = el.getBoundingClientRect();
      return rect.width > 0 && rect.height > 0;
    });
    console.log("Input visible:", inputVisible);
    
    if (inputVisible) {
      await page.type('#chat-input', 'Test message');
      console.log("Typed message");
      await page.click('.btn-send');
      console.log("Clicked send");
      
      // Wait a bit to see if there's any log or error
      await new Promise(r => setTimeout(r, 2000));
      
      // Check if message appeared in chat
      const chatHtml = await page.evaluate(() => {
        return document.querySelector('#chat-messages-container').innerHTML;
      });
      console.log("Chat contains Test message:", chatHtml.includes('Test message'));
    }
  } catch (err) {
    console.error('TEST ERROR:', err);
  }
  
  await browser.close();
})();
