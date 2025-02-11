from machine import Pin, Timer
import utime

g_ms12_pin_2 = Pin(8, Pin.OUT, value=1)         # FdB: Defines Pin MS1_2 as step 1/8 pins for motor 2 (DEC)
g_ms3_pin_2 = Pin(9, Pin.OUT, value=0)          # FdB: Defines Pin MS3 as step 1/16 pin

class Stepper_DEC:
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
 
step_pin_DEC = 15
dir_pin_DEC = 14
stepper_DEC = Stepper_DEC(dir_pin_DEC, step_pin_DEC)
 
def loop():
    stepper_DEC.move(-500, 8000, 2)  # 2 revolutions backward
    utime.sleep(1)
    stepper_DEC.move(500, 8000, 2)  # 2 revolutions backward
    utime.sleep(1)

if __name__ == '__main__':
    loop()