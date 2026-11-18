/*
* FPS (Fingerprint Security System) Firmware
* COPYRIGHT 2022-2026 SUJEB2 STUDIOS (Seungbin Kim)
*/

#include "fingerprint.h"

#define FIRMWAREVERSION "0.0.1"
#define HOST_BAUD 9600
#define SENSOR_BAUD 57600
#define FINGER_WAIT_MS 20000UL // give up waiting for a finger after this
#define IMAGE_RETRY 3          // bad images allowed per scan before failing
#define COMMAND_MAX_LEN 64
#define SCAN_INTERVAL_MS 100UL // idle sensor polling period

// door lock relay, change to match the wiring
#define LOCK_PIN 4             // GPIO driving the relay / lock driver
#define LOCK_ACTIVE HIGH       // level that OPENS the lock (LOW for active-low relay boards)
#define UNLOCK_MS 3000UL       // how long the lock stays open
#define UNLOCK_COMMAND "QR_UNLOCK" // must match [QRCode] UnlockCommand in conf.ini

#if (defined(__AVR__) || defined(ESP8266)) && !defined(__AVR_ATmega2560__) // serial module set
#define FINGERPRINT_LINE1 2
#define FINGERPRINT_LINE2 3
SoftwareSerial sensorSerial(FINGERPRINT_LINE1, FINGERPRINT_LINE2);
#elif defined(ESP32)
#define SENSOR_RX_PIN 25  // Connect to fingerprint sensor TX
#define SENSOR_TX_PIN 26  // Connect to fingerprint sensor RX
#define sensorSerial Serial2
#else
#define sensorSerial Serial1
#endif

Adafruit_Fingerprint module = Adafruit_Fingerprint(&sensorSerial);
bool sensorReady = false;
String command;

bool lockOpen = false;
unsigned long lockOpenedAt = 0;
unsigned long lastScanAt = 0;
bool fingerLatched = false; // a result was already sent for the finger on the sensor

void reply(const char *token) {
    Serial.println(token);
}

/* ---------- door lock ---------- */

void lockDoor() {
    digitalWrite(LOCK_PIN, LOCK_ACTIVE == HIGH ? LOW : HIGH);
    lockOpen = false;
}

void unlockDoor() {
    digitalWrite(LOCK_PIN, LOCK_ACTIVE);
    lockOpen = true;
    lockOpenedAt = millis(); // a second unlock while open restarts the timer
    Serial.println(F("LOG:door unlocked"));
}

void serviceLock() { // called from every wait loop so the door never stays open
    if (lockOpen && millis() - lockOpenedAt >= UNLOCK_MS) {
        lockDoor();
        Serial.println(F("LOG:door locked"));
    }
}

/* ---------- enrollment ---------- */

const char *waitForImage() {
    unsigned long start = millis();
    while (millis() - start < FINGER_WAIT_MS) {
        serviceLock();
        uint8_t p = module.getImage();
        if (p == FINGERPRINT_OK) return NULL;
        if (p != FINGERPRINT_NOFINGER && p != FINGERPRINT_IMAGEFAIL) return "FAILED"; // sensor communicate error
        delay(50);
    }
    return "TIMEOUT";
}

const char *waitForRemoval() {
    unsigned long start = millis();
    while (millis() - start < FINGER_WAIT_MS) {
        serviceLock();
        uint8_t p = module.getImage();
        if (p == FINGERPRINT_NOFINGER) return NULL;
        if (p != FINGERPRINT_OK && p != FINGERPRINT_IMAGEFAIL) return "FAILED";
        delay(50);
    }
    return "TIMEOUT";
}

const char *captureInto(uint8_t buffer) {
    for (uint8_t attempt = 0; attempt < IMAGE_RETRY; attempt++) {
        reply(buffer == 1 ? "PLACE_FINGER" : "PLACE_AGAIN");
        const char *err = waitForImage();
        if (err) return err;

        uint8_t p = module.image2Tz(buffer);
        if (p == FINGERPRINT_OK) {
            reply("CAPTURED");
            return NULL;
        }
        if (p == FINGERPRINT_PACKETRECIEVEERR) return "FAILED";

        reply("IMAGE_ERROR"); // could be messy image
        err = waitForRemoval();
        if (err) return err;
    }
    return "FAILED";
}

const char *enrollFingerprint(uint16_t slot) {
    Serial.print(F("LOG:enrolling slot #"));
    Serial.println(slot);
    reply("ENROLLMENT_STARTED");

    const char *err = captureInto(1);
    if (err) return err;

    reply("REMOVE_FINGER");
    err = waitForRemoval();
    if (err) return err;

    err = captureInto(2);
    if (err) return err;

    uint8_t p = module.createModel();
    if (p == FINGERPRINT_ENROLLMISMATCH) return "MISMATCH";
    if (p != FINGERPRINT_OK) return "FAILED";

    p = module.storeModel(slot);
    switch (p) {
    case FINGERPRINT_OK:
        module.getTemplateCount();
        Serial.print(F("LOG:templates stored "));
        Serial.println(module.templateCount);
        return "ENROLLED";
    case FINGERPRINT_BADLOCATION:
        return "BAD_LOCATION";
    case FINGERPRINT_FLASHERR:
        return "FLASH_ERROR";
    default:
        return "FAILED";
    }
}

/* ---------- idle scanning ---------- */

void scanFingerprint() {
    uint8_t p = module.getImage();
    if (p == FINGERPRINT_NOFINGER) {
        fingerLatched = false; // finger lifted, next touch is a new scan
        return;
    }
    if (p != FINGERPRINT_OK) {
        if (p != FINGERPRINT_IMAGEFAIL) {
            Serial.print(F("LOG:sensor error 0x"));
            Serial.println(p, HEX);
        }
        return;
    }
    if (fingerLatched) return; // same touch, already answered

    p = module.image2Tz(1);
    if (p != FINGERPRINT_OK) return; // messy or partial image, try again next poll

    fingerLatched = true;
    p = module.fingerSearch(1);
    if (p == FINGERPRINT_OK) {
        Serial.print(F("LOG:match confidence "));
        Serial.println(module.confidence);
        Serial.print(F("SUCCESS:")); // matched sensor slot, the host maps it to a user
        Serial.println(module.fingerID);
        unlockDoor();
    } else if (p == FINGERPRINT_NOTFOUND) {
        reply("NOT_FOUND");
    } else {
        fingerLatched = false; // communication error, retry this touch
        Serial.print(F("LOG:search error 0x"));
        Serial.println(p, HEX);
    }
}

/* ---------- host commands ---------- */

void handleCommand(String cmd) {
    cmd.trim();
    if (cmd.length() == 0) return;
    String upper = cmd;
    upper.toUpperCase();

    if (upper == "PING") {
        reply(sensorReady ? "READY" : "SENSOR_NOT_FOUND");
        return;
    }

    if (upper == UNLOCK_COMMAND) { // qrcode approved on the host, works without the sensor
        unlockDoor();
        reply("READY");
        return;
    }

    if (!sensorReady) {
        reply("SENSOR_NOT_FOUND");
        return;
    }

    if (upper.startsWith("ENROLL:")) {
        long slot = cmd.substring(7).toInt(); // 0 when not a number
        uint16_t capacity = module.capacity ? module.capacity : 127;
        if (slot < 1 || slot >= capacity) {
            reply("BAD_LOCATION");
        } else {
            reply(enrollFingerprint((uint16_t)slot));
        }
        fingerLatched = true; // finger may still be down, don't scan it as a login
        reply("READY");
    } else {
        Serial.print(F("LOG:unknown command "));
        Serial.println(cmd);
    }
}

void setup() {
    pinMode(LOCK_PIN, OUTPUT);
    lockDoor(); // locked before anything else

    Serial.begin(HOST_BAUD);
    while (!Serial)
        ; // For Yun/Leo/Micro/Zero/...
    delay(100);
    Serial.print(F("LOG:firmware version "));
    Serial.println(F(FIRMWAREVERSION));

    #if defined(ESP32)
        sensorSerial.begin(SENSOR_BAUD, SERIAL_8N1, SENSOR_RX_PIN, SENSOR_TX_PIN);
        delay(1000);  // Give the fingerprint sensor time to boot
    #else
        module.begin(SENSOR_BAUD);
    #endif
    if (!module.verifyPassword()) {
        reply("SENSOR_NOT_FOUND"); // keep running so the host still gets an answer
        return;
    }

    module.getParameters();
    module.getTemplateCount();
    Serial.print(F("LOG:capacity "));
    Serial.print(module.capacity);
    Serial.print(F(", security level "));
    Serial.print(module.security_level);
    Serial.print(F(", templates stored "));
    Serial.println(module.templateCount);

    sensorReady = true;
    reply("READY");
}

void loop() {
    while (Serial.available() > 0) {
        char c = Serial.read();
        if (c == '\n' || c == '\r') {
            if (command.length() > 0) handleCommand(command);
            command = "";
        } else if (command.length() < COMMAND_MAX_LEN) {
            command += c;
        }
    }

    serviceLock();

    if (sensorReady && millis() - lastScanAt >= SCAN_INTERVAL_MS) {
        lastScanAt = millis();
        scanFingerprint();
    }
}
