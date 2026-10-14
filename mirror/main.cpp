// Display mirror. The PC simulator owns the UI. This firmware paints RGB565
// strips on the ILI9341 and reports XPT2046 touches back to the PC.

#include <Arduino.h>
#include <TFT_eSPI.h>
#include <esp_crc.h>

static TFT_eSPI tft;
static const int SCREEN_W = 240;
static const int SCREEN_H = 320;
static const int MAX_ROWS = 8;
static uint16_t pixels[MAX_ROWS * SCREEN_W];
static bool linked = false;
// Same rotation-0 calibration as include/touch_calibration.h. Flag 2 inverts X.
static uint16_t touchCal[5] = {418, 3255, 338, 3334, 2};

static bool readLine(char *buf, size_t cap, uint32_t timeoutMs) {
    size_t n = 0;
    uint32_t start = millis();
    while (millis() - start < timeoutMs) {
        while (Serial.available()) {
            int c = Serial.read();
            if (c < 0) break;
            if (c == '\n') {
                buf[n] = 0;
                return true;
            }
            if (c != '\r' && n + 1 < cap) buf[n++] = (char)c;
            start = millis();
        }
        delay(1);
    }
    buf[n] = 0;
    return false;
}

static bool readExact(uint8_t *dst, size_t need, uint32_t timeoutMs) {
    size_t got = 0;
    uint32_t start = millis();
    while (got < need && millis() - start < timeoutMs) {
        int chunk = Serial.readBytes(dst + got, need - got);
        if (chunk > 0) {
            got += (size_t)chunk;
            start = millis();
        }
    }
    return got == need;
}

static void reportTouch() {
    uint16_t x = 0, y = 0;
    bool down = tft.getTouch(&x, &y);
    static bool wasDown = false;
    static uint16_t lastX = 0, lastY = 0;
    static uint32_t lastSent = 0;
    if (!down) {
        if (!wasDown) return;
        Serial.printf("@@TOUCH %u %u 0\n", lastX, lastY);
        wasDown = false;
        return;
    }
    if (x >= SCREEN_W) x = SCREEN_W - 1;
    if (y >= SCREEN_H) y = SCREEN_H - 1;
    int dx = (int)x - (int)lastX;
    int dy = (int)y - (int)lastY;
    if (dx < 0) dx = -dx;
    if (dy < 0) dy = -dy;
    bool moved = !wasDown || dx + dy >= 2;
    if (!moved && millis() - lastSent < 40) return;
    Serial.printf("@@TOUCH %u %u 1\n", x, y);
    lastX = x;
    lastY = y;
    wasDown = true;
    lastSent = millis();
}

static void paint(int y, int h) {
    tft.startWrite();
    tft.setAddrWindow(0, y, SCREEN_W, h);
    tft.pushColors(pixels, (uint32_t)(SCREEN_W * h), true);
    tft.endWrite();
}

void setup() {
    Serial.setRxBufferSize(16 * 1024);
    Serial.setTimeout(20);
    Serial.begin(921600);
    tft.begin();
    tft.setRotation(0);
    tft.setTouch(touchCal);
    tft.fillScreen(TFT_BLACK);
}

void loop() {
    static char line[96];
    if (!linked) {
        static uint32_t announced = 0;
        if (millis() - announced > 400) {
            Serial.println("@@MIRROR 2 240 320");
            announced = millis();
        }
        if (!readLine(line, sizeof(line), 40)) return;
        if (strcmp(line, "HELLO") == 0) {
            linked = true;
            Serial.println("@@OK");
        }
        return;
    }

    reportTouch();
    if (!readLine(line, sizeof(line), 20)) return;
    if (strcmp(line, "HELLO") == 0 || strcmp(line, "VER") == 0) {
        Serial.println(line[0] == 'H' ? "@@OK" : "@@MIRROR 2 240 320");
        return;
    }
    int y = 0, h = 0;
    unsigned long crc = 0;
    if (sscanf(line, "PIX %d %d %lu", &y, &h, &crc) != 3 || y < 0 || h < 1 || h > MAX_ROWS || y + h > SCREEN_H) {
        Serial.println("@@ERR");
        return;
    }
    size_t bytes = (size_t)h * SCREEN_W * 2;
    if (!readExact(reinterpret_cast<uint8_t *>(pixels), bytes, 1000) ||
        esp_crc32_le(0, reinterpret_cast<uint8_t *>(pixels), bytes) != (uint32_t)crc) {
        Serial.println("@@ERR");
        return;
    }
    paint(y, h);
    Serial.println("@@OK");
}
