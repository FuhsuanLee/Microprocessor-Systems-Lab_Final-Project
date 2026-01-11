const express = require('express');
const { spawn, execSync, exec } = require('child_process');
const path = require('path');
const fs = require('fs');

const LOG_DEVICE = '/dev/log_driver';
const DRIVER_PATH = path.join(__dirname, 'driver', 'log_driver.ko');

function log_message(entry) {
    fs.writeFile(LOG_DEVICE, entry, { flag: 'a' }, (err) => {
        if (err) console.error('Log write error:', err);
    });
    console.log(entry.trim());
}

const app = express();
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// --- Python 腳本 ---
const PYTHON_GPIO = path.join(__dirname, 'utils', 'gpio_control.py');
const PYTHON_CAMERA = path.join(__dirname, 'utils', 'camera_control.py');

// ===== 自動載入 kernel driver =====
try {
    execSync(`sudo insmod ${DRIVER_PATH}`);
    log_message('Kernel driver loaded');
} catch (e) {
    console.error('Failed to load kernel driver:', e);
}

// 啟動 GPIO 常駐進程
const gpioProcess = spawn('python3', [PYTHON_GPIO]);
gpioProcess.stdout.on('data', data => log_message('GPIO: ' + data.toString().trim()));
gpioProcess.stderr.on('data', data => console.error('GPIO Error:', data.toString()));

// ------------------- 主頁 -------------------
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// ------------------- 授權鎖 -------------------
let authResolve = null;
function waitForAuth() {
    return new Promise(resolve => { authResolve = resolve; });
}

app.post('/auth/approve', (req, res) => {
    if (authResolve) {
        authResolve();
        authResolve = null;
        res.json({ success: true });
        log_message('Authorization approved');
    } else {
        res.json({ success: false, msg: 'No pending request' });
    }
});

// ------------------- GPIO 指令 -------------------
function sendCommand(cmd) {
    return new Promise(resolve => {
        let handler = (data) => {
            gpioProcess.stdout.off('data', handler);
            resolve(data.toString().trim());
        }
        if (cmd.startsWith('read')) gpioProcess.stdout.on('data', handler);
        gpioProcess.stdin.write(cmd + '\n');
        if (!cmd.startsWith('read')) resolve('ok');
    });
}

// ------------------- API -------------------

// 1. LED 開
app.post('/led/on', async (req, res) => {
    try {
        const { leds } = req.body;
        for (const led of leds) {
            await sendCommand(`led ${led} on`);
            log_message('LED ' + led + ' turned on');
        }
        res.json({ success: true });
    } catch (e) {
        res.status(500).json({ success: false, error: e.message });
    }
});

// 2. LED 關
app.post('/led/off', async (req, res) => {
    try {
        const { leds } = req.body;
        for (const led of leds) {
            await sendCommand(`led ${led} off`);
            log_message('LED ' + led + ' turned off');
        }
        res.json({ success: true });
    } catch (e) {
        res.status(500).json({ success: false, error: e.message });
    }
});

// 3. 開門
app.post('/open', async (req, res) => {
    try {
        await waitForAuth();

        const pyProcess = spawn('python3', [PYTHON_CAMERA]);
        let result = false;
        let adcValue = null;

        pyProcess.stdout.on('data', (data) => {
            try {
                const obj = JSON.parse(data.toString().trim());
                result = obj.result;
                adcValue = obj.adc;
            } catch (e) {
            }
        });

        pyProcess.stderr.on('data', (data) => {
            console.error('Camera Error:', data.toString());
        });

        pyProcess.on('close', (code) => {
            res.json({
                success: result,
                adc: adcValue,
                msg: result ? 'Door open triggered' : 'No detection'
            });
            log_message('Door open attempt: ' + (result ? 'Success' : 'Failed') + ', ADC=' + adcValue);
        });

    } catch (e) {
        res.status(500).json({ success: false, error: e.message });
    }
});

// 4. 關門
app.post('/close', async (req, res) => {
    try {
        await waitForAuth();

        await sendCommand('blink 0.5 5');
        await sendCommand('close')

        res.json({ success: true, msg: 'Door closed' });
        log_message('Door closed');
    } catch (e) {
        res.status(500).json({ success: false, error: e.message });
    }
});

// 5. 讀取 Log
app.get('/logs', (req, res) => {
    exec('cat /dev/log_driver', (error, stdout, stderr) => {
        if (error) {
            console.error(`exec error: ${error}`);
            return res.status(500).json({ error: 'Failed to read logs' });
        }
        res.json({ logs: stdout });
    });
});

// ------------------- 安全退出 -------------------
function shutdown() {
    console.log('Shutting down...');
    sendCommand('stop');
    sendCommand('exit');
    gpioProcess.kill();

    // 卸載 kernel driver
    try {
        execSync('sudo rmmod log_driver');
        log_message('Kernel driver unloaded');
    } catch (e) {
        console.error('Failed to unload kernel driver:', e);
    }

    process.exit();
}

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);

app.listen(3000, () => log_message('Smart Home Server running on port 3000'));
