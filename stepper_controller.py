         ### Libraries ###
import time                      # To be able to add delays (sleep)
from machine import Pin          # To allow software to manipulate board pins
import rp2                       # Is used to make PIO programs

         ### Global Variables ###
motor_1 = False                   # To be able to check if a motor is completed
motor_2 = False                   # - " -

x_last = 0                        # To store relative position in steps
y_last = 0                        # - " -

# x_speed = 10                      # Speed of motor to put into PIO.
# y_speed = 10                      # - " -


         ### Stepper motor setup ###
# These settings are made for rotational movement only. (Belts, gears etc)
# This means if you want to use a trapetziod for a linear actuator, use the other motor settings.
drv_ms = 16                # resolution of microstepping 1 / 1, 2, 4, 8, 16, 32, 64, 128, write the denominator only
motor_steps_per_rev = 200 # steps per full revolution, often 200 or 400
gear_ratio = 9.9375            # how many times the motor needs to spin to turn output one time. Gear ratio 5:1 means 5 times for one full turn
steps_per_rev = motor_steps_per_rev * drv_ms * gear_ratio # This is the number of steps to move output.
step_angle = 360 / steps_per_rev # This is the step resolution in degrees
lead_screw_pitch = 2 # This is how far each rotation will move something. 2 [mm] pitch is common for 3D printers.
step_pitch = lead_screw_pitch / steps_per_rev # This is how far along the lead screw we are moved for each step.
print("For gears, belts and arms.")
print("Steps per revolution:", steps_per_rev, "steps.",
      "\nOne step is", step_angle, "degrees.\n")
print("For lead screws.")
print ("[mm] per revolution:", lead_screw_pitch,
       "\nOne steps is", step_pitch, "[mm].\n")

# Whith the example above, we get:
# Belt, Gear or Arm 
# Steps per revolution: 3200
# Wormgear or Lead screw
# [mm] per revolution: 2
# One step is 0.1125 degrees


         ### Synchronization Pin ###
activation_pin = Pin(22, Pin.OUT) # Pin 25 is used to trigger our PIO programs/functions
                                  # and is mandatory to have synchronous activation of motors
                                  # For Pi Pico W, chose another Pin and add LED activation for
                                  # visual feedback.
                                  # *** FdB: changed to Pin 22 for Pi Pico W 

         ### PIO functions ###
# step_counter is a PIO program that takes in a value (desired number of steps)
# by pulling it from FIFO placing it in OSR,
# then copying it over to X and iterates over x until
# it reaches 0, whichs means all steps have been made.
# after each steps, a second PIO program within the same PIO-block
# is called which adds a delay to slow down the steps.
#
#      The available blocks and their state machines are:
#           -- PIO block 0 --           -- PIO block 1 --
#        State machine 0, 1, 2, 3    State machine 4, 5, 6, 7

@rp2.asm_pio(sideset_init=rp2.PIO.OUT_LOW) # Assembly decorator, sideset pin default Low
                                           # and that it's assigned Pin should be Low / Off 
                                           # when the program starts.
def step_counter():
    pull(block)                    # wait for FIFO to fill (put), then pull data to OSR
    mov(x, osr)                    # copy OSR data into X (load our steps into x)
    wait(1, gpio, 22)              # waiting for Pin 25 to activate, *** FdB: changed to Pin 22 for Pi Pico W
    label("count")                 # this is a header we jump back to for counting steps
    jmp(not_x, "end") .side(1) [1] # if x is 0(zero), jmp to end - Side Step Pin On
    irq(5) .side(0)                # sets IRQ 5 high, starting step_speed() - Side Step Pin Off
    irq(block, 4)                  # waiting for IRQ flag 4 to clear
    jmp(x_dec, "count")            # if x is NOT 0(zero), remove one (-1) from x and jump back to count, Else, continue
    label("end")                   # This is a header we can jmp to if x is 0.
    irq(block, rel(0))             # Signals IRQ handler that all steps have been made and waits for handler to clear the flag (block)

@rp2.asm_pio(autopull=True)                         # Tells the program that this is a PIO program/function.
def step_speed():
    wait(1, irq, 5)         # waiting for IRQ flag 5 from step_counter and then clears it
    set(y, 31)               # set y to the value 31 (which is 0-31 = 32), *** FdB: old value was 5, changed to 31
    label("delay")          # this is a header we jump back to for adding a delay
    nop() [20]               # do nothing for [n] instructions (which is 20 instructions), *** FdB: old value was 9, changed to 20
    jmp(y_dec, "delay")     # if y not 0(zero), remove one (-1) from y make jump to delay, Else, continue
    irq(clear, 4)           # clear IRQ flag 4, allowing step_counter() to continue

     ### PIO interupt handlers ###
# These are triggered by step_counter in each PIO block and thus
# there are two similar functions that does the same thing.
# When they are triggered, motor_n turns True and
# they print x or y steps to REPL and which statemachine is done.
def pio_0_handler(sm): # Motor 1
    global motor_1
    motor_1 = True
    print(sm, "x:", x_last)

def pio_1_handler(sm): # Motor 2
    global motor_2
    motor_2 = True
    print(sm, "y:", y_last)

     ### Setting up state machines ###
# Motor 1 is separated in the code to better explain each step.
# Motor 2 uses the same code, but is written in a much more readable way.
# Motor 2 is the prefered way to write code.
sc_freq = 1_000_000 # step_counter frequency
ss_freq = 1_000_000 # step_speed frequency
                    # 1_000_000 Hz = 1 MHz means each instruction in PIO is 1us long
                    # 4_000_000 Hz = 4 MHz means each instruction in PIO is 0.25 us long
# Motor 1 - Pio Block 0
step_pin_1 = Pin(11, Pin.OUT)        # Defines Pin X as step pin
dir_pin_1 = Pin(10, Pin.OUT)         # Defines Pin Y as direction pin of motor 1 and as an Output pin
sm_0 = rp2.StateMachine(0,           # Creates object called sm_0 and binds it to state machine 0 inPIO block 0
                        step_counter,                    # Assigns step_counter as PIO program/function
                        freq=sc_freq,                    # Sets the PIO frequency to sc_freq
                        sideset_base=step_pin_1          # Sets Pin X as first sideset pin of PIO program/function
                        )

sm_0.irq(pio_0_handler)              # Directs interrupts from sm_0 to the interrupt handler pio_0_handler()
sm_1 = rp2.StateMachine(1,           # Creates object called sm_1 and binds it to state machine 1 in PIO block 0
                        step_speed,  # Assigns step_speed as PIO program/function
                        freq=ss_freq # Sets the PIO frequency to ss_freq
                        )

# Motor 2 - Pio Block 1
step_pin_2 = Pin(15, Pin.OUT)                                                  # Step Pin 
dir_pin_2 = Pin(14, Pin.OUT)                                                   # Direction Pin 
sm_4 = rp2.StateMachine(4, step_counter, freq=sc_freq, sideset_base=step_pin_2) # Statemachine 4 - PIO block 1
sm_4.irq(pio_1_handler)                                                        #
sm_5 = rp2.StateMachine(5, step_speed, freq=ss_freq)                        # Statemachine 5 - PIO block 1

# Activating all state machine
sm_0.active(1), sm_1.active(1) # Motor 1 State machine 0 and 1 in PIO block 0
sm_4.active(1), sm_5.active(1) # Motor 2 State machine 4 and 5 in PIO block 1

def steps(x, y): # Feeds the PIO programs and activates them.
    global motor_1, motor_2
    global x_last, y_last
    x_last = x + x_last
    y_last += y # same but shorter notation
    motor_1 = False
    motor_2 = False
    x_steps = round(x)
    y_steps = round(y)
    if int(x) < 0:
        dir_pin_1.value(1)
        x_steps = x_steps * (-1)
    if int(y) < 0:
        dir_pin_2.value(1)
        y_steps = y_steps * (-1)
    sm_0.put(x_steps)
    sm_4.put(y_steps)
#     sm_1.put(x_speed)
#     sm_5.put(y_speed)
    activation_pin.value(1)
    print("\n### Stepping the steps ###")
    print("\nstepping to: " + "\nx:" +  str(x_last) + "\ny:" + str(y_last))
    while True:
        if motor_1 and motor_2:
            dir_pin_1.value(0)
            dir_pin_2.value(0)
            activation_pin.value(0) # This is active until both processes have signaled that they are done.
            position()
            return
        time.sleep_ms(1)

# def steps(x, y, z, r):
#     x_steps = int(x)
#     y_steps = int(y)
#     z_steps = int(z)
#     r_steps = int(r)
#     steps(x_steps, y_steps, z_steps, r_steps)


def angle(x_deg, y_deg):
    global step_angle
    x_steps = round(x_deg / step_angle)
    y_steps = round(y_deg / step_angle)
    steps(x_steps, y_steps)

def instructor(aquired_tuple):
    instruction_tuple = aquired_tuple
    for i in range(len(instruction_tuple)): # loads each item within the instruction tuple and assign to each motor.
        x = int(instruction_tuple[i][0])
        y = int(instruction_tuple[i][1])
        steps(x, y)

def position(x = 0, y = 0):
    global x_last, y_last
    x_angle = step_angle * x_last
    y_angle = step_angle * y_last
    if x != 0 and y != 0: #and z != 0 and r != 0:
#         print("x at:", x_angle, "\u00B0")
#         print("y at:", y_angle, "\u00B0")
        return x_angle, y_angle #, z_angle, r_angle
    elif x != 0:
#         print("x at:", x_angle, "\u00B0")
        return x_angle
    elif y != 0:
#         print("y at:", y_angle, "\u00B0")
        return y_angle
    else:
        print("x at:", x_angle, "\u00B0")
        print("y at:", y_angle, "\u00B0")

def zero():
    angle(-1 * position (1, 0), -1 * position (0, 1))

# def motor_speed(x, y, z, r):
#     global x_speed, y_speed, z_speed, r_speed
#     min_limit = 5
#     max_limit = 1000
#     if min_limit <= x <= max_limit:
#         x_speed = x
#     if min_limit <= y <= max_limit:
#         y_speed = y
#     if min_limit <= z <= max_limit:
#         z_speed = z
#     if min_limit <= r <= max_limit:
#         r_speed = r

if __name__ == "__main__":
    machine.freq(250_000_000)
    print(machine.freq()/1000000, "MHz clock-speed")
    #input("\nPress any key to test:\ninstructor()")
    instructor(((20, -20), (-20, 20)))
