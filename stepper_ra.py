from machine import Pin, Timer
import utime

g_ms12_pin_1 = Pin(6, Pin.OUT, value=1)         # FdB: Defines Pin MS1_2 as step 1/8 pins for motor 1 (RA)
g_ms3_pin_1 = Pin(7, Pin.OUT, value=0)          # FdB: Defines Pin MS3 as step 1/16 pin
 
class Stepper_RA:
    def __init__(self, dir_pin, step_pin):
        self.dir_pin = Pin(dir_pin, Pin.OUT)
        self.step_pin = Pin(step_pin, Pin.OUT)
        self.position = 0
 
    def move(self, steps, delay, accel):
        min_delay = 100
        max_delay = delay
        if steps > 0:
            self.dir_pin.value(1)
            self.position += steps
        else:
            self.dir_pin.value(0)
            self.position -=steps

        steps = abs(steps)

        for i in range(steps):
            self.step_pin.value(1)
            utime.sleep_us(delay)
            self.step_pin.value(0)
            utime.sleep_us(delay)

            if i < steps // 2 and delay > min_delay:
                delay -= accel
            elif i >= steps // 2 and delay < max_delay:
                delay += accel

if __name__ == '__main__':
    loop()