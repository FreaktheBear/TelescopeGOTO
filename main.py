import asyncio
import os
import machine
from time import sleep
from machine import Pin, UART


# ---------------- Variable Decleration ------------------



# ---------------- Async:Read Serial Data ------------------
# receiver.py / Tx/Rx => Tx/Rx
async def read_serial():

    #uart = machine.UART(0, 9600)
    uart = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1))
    uart.init(bits=8, parity=None, stop=1)
    print(uart)
    RA = '19:50:57#'
    DEC = '-25"58:14#'
    LX200_command = None

    while True:
        if uart.any(): 
            LX200_command = uart.read()
            print(LX200_command)
            try:                
                if LX200_command == b'#:GR#':
                    print(RA)
                    uart.write(RA)
                elif LX200_command == b"#:GD#":
                    print(DEC)
                    uart.write(DEC)
                else:
                    pass
            except:
                pass
        await asyncio.sleep_ms(500)

# ---------------- Main Program Loop ------------------
async def main():
    asyncio.create_task(read_serial())
    
    while True:
        try:
            if True:
                print("Main program running")
                await asyncio.sleep_ms(1000)   # Sleep for 1 seconds
        except OSError as e:
            print('Main error')
        await asyncio.sleep_ms(100)   # Sleep for 0.1 seconds

try:
    asyncio.run(main())  # Run the main asynchronous function
except OSError as e:
    print('Runtime error')
finally:
    asyncio.new_event_loop() #Create a new event loop


