#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import Jetson.GPIO as GPIO
import time
import sys
import threading
import queue
import atexit

# GPIO 定義
LED1_PIN = 27
LED2_PIN = 5
LED3_PIN = 13
LED4_PIN = 21
LED_PINS = {0: LED1_PIN, 1: LED2_PIN, 2: LED3_PIN, 3: LED4_PIN}

def init_gpio():
    GPIO.setwarnings(False)
    GPIO.cleanup()
    GPIO.setmode(GPIO.BCM)
    for pin in LED_PINS.values():
        GPIO.setup(pin, GPIO.OUT)

def control_led(led_index, state):
    if led_index not in LED_PINS:
        return
    GPIO.setup(LED_PINS[led_index], GPIO.OUT)
    GPIO.output(LED_PINS[led_index], GPIO.HIGH if state else GPIO.LOW)

def blink_leds_pair_step(pair_state):
    pair1, pair2 = [0,1], [2,3]
    if pair_state == 0:
        for i in pair1: GPIO.output(LED_PINS[i], GPIO.HIGH)
        for i in pair2: GPIO.output(LED_PINS[i], GPIO.LOW)
    else:
        for i in pair1: GPIO.output(LED_PINS[i], GPIO.LOW)
        for i in pair2: GPIO.output(LED_PINS[i], GPIO.HIGH)

def stop_leds():
    for pin in LED_PINS.values():
        GPIO.output(pin, GPIO.LOW)

# ---- 非阻塞隊列 ----
task_queue = queue.Queue()
blink_task = None

def task_worker():
    pair_state = 0
    while True:
        global blink_task
        if blink_task:
            blink_leds_pair_step(pair_state)
            pair_state ^= 1
            blink_task['remaining'] -= 1
            if blink_task['remaining'] <= 0:
                blink_task = None
            time.sleep(blink_task['delay'] if blink_task else 0.5)
            continue

        try:
            task = task_queue.get(timeout=0.1)
        except queue.Empty:
            continue

        cmd = task['cmd']
        if cmd == 'led':
            control_led(task['led_index'], task['state'])
        elif cmd == 'leds':
            for idx in task['led_indices']:
                control_led(idx, task['state'])
        elif cmd == 'blink':
            blink_task = {'delay': task['delay'], 'remaining': task['count']}
        elif cmd == 'stop':
            stop_leds()
        elif cmd == 'exit':
            stop_leds()
            sys.exit(0)

def process_command(cmd_line):
    parts = cmd_line.strip().split()
    if not parts: return
    cmd = parts[0]
    if cmd == 'led':
        task_queue.put({'cmd':'led', 'led_index':int(parts[1]), 'state':parts[2].lower()=='on'})
    elif cmd == 'leds':
        task_queue.put({'cmd':'leds', 'led_indices':[int(x) for x in parts[1].split(',')], 'state':parts[2].lower()=='on'})
    elif cmd == 'blink':
        delay = float(parts[1]) if len(parts)>1 else 1
        count = int(parts[2]) if len(parts)>2 else 10
        task_queue.put({'cmd':'blink','delay':delay,'count':count})
    elif cmd in ['stop','exit']:
        task_queue.put({'cmd':cmd})

def cleanup():
    stop_leds()
    GPIO.cleanup()
    print("GPIO cleaned up", flush=True)

atexit.register(cleanup)

if __name__ == "__main__":
    init_gpio()
    print("GPIO Service Started", flush=True)
    threading.Thread(target=task_worker, daemon=True).start()
    for line in sys.stdin:
        process_command(line)
