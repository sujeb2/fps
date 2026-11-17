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

#if (defined(__AVR__) || defined(ESP8266)) && !defined(__AVR_ATmega2560__) // serial module set
#define FINGERPRINT_LINE1 2
#define FINGERPRINT_LINE2 3
SoftwareSerial sensorSerial(FINGERPRINT_LINE1, FINGERPRINT_LINE2);
#elif defined(ESP32)
#define sensorSerial Serial2 // RX GPIO16, TX GPIO17. Serial1's default pins are wired to flash on ESP32
#else
#define sensorSerial Serial1
#endif

Adafruit_Fingerprint module = Adafruit_Fingerprint(&sensorSerial);
bool sensorReady = false;
String command;

void reply(const char *token) {
    Serial.println(token);
}

const char *waitForImage() {
    unsigned long start = millis();
    while (millis() - start < FINGER_WAIT_MS) {
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
        return "ENROLLED";
    case FINGERPRINT_BADLOCATION:
        return "BAD_LOCATION";
    case FINGERPRINT_FLASHERR:
        return "FLASH_ERROR";
    default:
        return "FAILED";
    }
}

void handleCommand(String cmd) {
    cmd.trim();
    String upper = cmd;
    upper.toUpperCase();

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
        reply("READY");
    } else if (upper == "PING") {
        reply("READY");
    } else if (upper = "") {

    } else {
        Serial.print(F("LOG:unknown command "));
        Serial.println(cmd);
    }
}

void setup() {
    Serial.begin(HOST_BAUD);
    while (!Serial)
        ; // For Yun/Leo/Micro/Zero/...
    delay(100);
    Serial.print(F("LOG:firmware version "));
    Serial.println(F(FIRMWAREVERSION));

    module.begin(SENSOR_BAUD);
    if (!module.verifyPassword()) {
        reply("SENSOR_NOT_FOUND"); // keep running so the host still gets an answer
        return;
    }

    module.getParameters();
    Serial.print(F("LOG:capacity "));
    Serial.print(module.capacity);
    Serial.print(F(", security level "));
    Serial.print(module.security_level);
    Serial.print(F(", templates stored "));
    module.getTemplateCount();
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
}
