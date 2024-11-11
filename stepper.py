import rp2
from machine import Pin

# ------------------ Config of PIO for Stepper Control ------------------ #
@rp2.asm_pio(set_init=rp2.PIO.OUT_LOW)
def stepper():
  pull(noblock) # pull the latest data into osr or put current x into osr if queue is empty
  mov(x, osr) # copy osr into x
  mov(y, x) # copy x into y to reset later

  jmp(not_x, "end") # if x is empty skip the step

  set(pins, 1) [1] # enable pin, A4988 needs 2us pulse, so wait additional 1us here
  set(pins, 0) # end the pulse
  irq(0) # invoke interrupt

  label("delay")
  jmp(x_dec, "delay") # loop and decrement x until it's 0
  
  label("end")
  mov(x, y) # restore x, which is 0 at this point

# regular nema stepper has 200 steps per revolution, with 32 microstepping mode it's 6400 steps per revolution
class Stepper:
    
  def __init__(self, id, dir_pin, step_pin, step_callback = None):
    self.dir_pin = Pin(dir_pin, Pin.OUT)
    # at 1_000_000Hz clock a single instruction is 1us
    self._sm = rp2.StateMachine(id, stepper, freq=1_000_000, set_base=Pin(step_pin, Pin.OUT))

    if step_callback is not None:
      self._sm.irq(step_callback)
    
    self._sm.put(0)
    self._sm.active(1)

  def set_steps_per_second(self, steps_per_second):
    if steps_per_second == 0:
      self._sm.put(0)
      return

    if steps_per_second > 0:
      self.dir_pin.high()
    elif steps_per_second < 0:
      self.dir_pin.low()

    delay = abs(round(1_000_000 / steps_per_second)) - 10 # there are 10 instructions in the program for each step
    self._sm.put(delay)