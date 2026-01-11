#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import os
import requests
import sys
import time
import json
import Jetson.GPIO as GPIO

# GPIO LED & 光敏電阻定義
SPICLK = 11
SPIMISO = 9
SPIMOSI = 10
SPICS = 8
LED1_PIN = 27
LED2_PIN = 5
LED3_PIN = 13
LED4_PIN = 21
LED_PINS = {0: LED1_PIN, 1: LED2_PIN, 2: LED3_PIN, 3: LED4_PIN}
PHOTO_CHANNEL = 0

def init_gpio():
    GPIO.setwarnings(False)
    GPIO.cleanup()
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(SPIMOSI, GPIO.OUT)
    GPIO.setup(SPIMISO, GPIO.IN)
    GPIO.setup(SPICLK, GPIO.OUT)
    GPIO.setup(SPICS, GPIO.OUT)
    for pin in LED_PINS.values():
        GPIO.setup(pin, GPIO.OUT)

def stop_leds():
    for pin in LED_PINS.values():
        GPIO.output(pin, GPIO.LOW)

def blink_leds_pair(times=2, delay=0.3):
    pair1, pair2 = [0,1], [2,3]
    for _ in range(times):
        for i in pair1: GPIO.output(LED_PINS[i], GPIO.HIGH)
        for i in pair2: GPIO.output(LED_PINS[i], GPIO.LOW)
        time.sleep(delay)
        for i in pair1: GPIO.output(LED_PINS[i], GPIO.LOW)
        for i in pair2: GPIO.output(LED_PINS[i], GPIO.HIGH)
        time.sleep(delay)
    stop_leds()

def read_adc():
    GPIO.output(SPICS, True)
    GPIO.output(SPICLK, False)
    GPIO.output(SPICS, False)

    commandout = PHOTO_CHANNEL | 0x18
    commandout <<= 3

    for _ in range(5):
        GPIO.output(SPIMOSI, bool(commandout & 0x80))
        commandout <<= 1
        GPIO.output(SPICLK, True)
        GPIO.output(SPICLK, False)

    adcout = 0
    for _ in range(12):
        GPIO.output(SPICLK, True)
        GPIO.output(SPICLK, False)
        adcout <<= 1
        if GPIO.input(SPIMISO):
            adcout |= 0x01

    GPIO.output(SPICS, True)
    return adcout >> 1

# --- Camera + Detect API ---
def capture_image(filename="images/capture.jpg"):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    try:
        cmd = f"gst-launch-1.0 nvarguscamerasrc num-buffers=1 ! nvvidconv ! jpegenc ! filesink location={filename}"
        subprocess.run(cmd, shell=True, check=True, timeout=10)
        return True
    except Exception as e:
        print(f"Capture failed: {e}", file=sys.stderr)
        return False

def detect_image(image_path="images/capture.jpg", endpoint="http://172.20.10.3:8000/detect"):
    try:
        import base64

        with open(image_path, "rb") as f:
            image_bytes = f.read()

        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        payload = {
            "image_base64": image_base64
        }

        headers = {
            "Content-Type": "application/json"
        }

        response = requests.post(endpoint, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        result = response.json()
        return result.get("result", False)
    except Exception as e:
        print(f"Detect API failed: {e}", file=sys.stderr)
        return False

def main():
    init_gpio()
    adc_value = 0
    result = False
    try:
        if capture_image():
            detected = detect_image()
            adc_value = read_adc()
            light_trigger = adc_value > 100  # 光敏電阻門檻
            if detected and light_trigger:
                blink_leds_pair(times=4, delay=0.3)  # 閃爍 LED 4 次
                result = True
    finally:
        stop_leds()
        GPIO.cleanup()
        # 回傳 JSON 給 Node.js
        print(json.dumps({"result": result, "adc": adc_value}))

if __name__ == "__main__":
    main()
