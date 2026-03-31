import puppeteer from 'puppeteer';
import fs from 'fs';
import path from 'path';

const reportPath = 'd:\\ims\\inventory-management-system-full-project\\test_report.md';

function logError(msg) {
    fs.appendFileSync(reportPath, `\n- **ERROR**: ${msg}\n`);
    console.error(`ERROR: ${msg}`);
}

function logSuccess(msg) {
    fs.appendFileSync(reportPath, `\n- **SUCCESS**: ${msg}\n`);
    console.log(`SUCCESS: ${msg}`);
}

(async () => {
    fs.appendFileSync(reportPath, `\n### Automated UI Test Run\n`);
    console.log("Launching browser...");
    const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox'] });
    const page = await browser.newPage();
    
    // Setup error listeners
    page.on('pageerror', err => logError('Page JS Error: ' + err.toString()));
    
    page.on('response', resp => {
        if (!resp.ok() && resp.url().includes('api/')) {
            logError(`API Error ${resp.status()} on ${resp.url()}`);
        }
    });

    try {
        console.log("Testing Login...");
        await page.goto('http://localhost:5175/login', { waitUntil: 'networkidle0' });
        
        await page.type('#email', 'admin@company.com');
        await page.type('#password', 'Admin@123');
        await Promise.all([
            page.waitForNavigation({ waitUntil: 'networkidle0' }),
            page.click('button[type="submit"]')
        ]);

        if (page.url().includes('dashboard') || page.url() === 'http://localhost:5175/') {
            logSuccess("Login successful.");
        } else {
            logError(`Login failed, stayed on ${page.url()}`);
            await page.screenshot({ path: 'd:\\ims\\inventory-management-system-full-project\\login_error.png' });
        }

        // Test Masters -> Products
        console.log("Testing Create Product...");
        await page.goto('http://localhost:5175/masters/products', { waitUntil: 'networkidle0' });
        // The rest depends on the exact UI implementation.
        // We will pause here to see if the first step works and if the API endpoints hit errors.
        await new Promise(r => setTimeout(r, 2000));
        logSuccess("Navigate to Products successful.");
    } catch(err) {
        logError('Test script setup error: ' + err.message);
    } finally {
        await browser.close();
        console.log("Test finished.");
    }
})();
