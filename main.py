import asyncio
import os
import machine
from time import sleep


# ---------------- Variable Decleration ------------------



# ---------------- Read Serial Data ------------------
# receiver.py / Tx/Rx => Tx/Rx
async def read_serial():

    uart = machine.UART(0, 9600)
    print(uart)
    ste = None
    msg = ""


    while True:
        if uart.any():
            b = uart.readline()
            print(type(b))
            print(b)
            try:
                msg = b.decode('utf-8')
                print(type(msg))
                print(">> " + msg)
                if msg == "e":

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


