from machine import Pin, Timer
import utime
 
class Stepper:

    steps = 0
    delay = 0
    accel = 0

    def __init__(self, dir_pin, step_pin):
        self.dir_pin = Pin(dir_pin, Pin.OUT)
        self.step_pin = Pin(step_pin, Pin.OUT)
        self.position = 0

    def move(self, steps, delay, accel):
        max_delay = delay
        self.dir_pin.value(1 if steps > 0 else 0)
        steps = abs(steps)
        for i in range(steps):
            self.step_pin.value(1)
            utime.sleep_us(delay)
            self.step_pin.value(0)
            utime.sleep_us(delay)
            if i < steps // 2 and delay > 100:
                delay -= accel
            elif i >= steps // 2 and delay < max_delay:
                delay += accel
        self.position += steps if steps > 0 else -steps


