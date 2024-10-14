import asyncio
import os
import machine
import utime, time
from machine import Pin, UART


# ---------------- Variable Decleration ------------------
g_latitude = 0.0
g_longitude = 0.0

# ---------------- Async:Read Serial Data from NEO-7M GPS ------------------
async def read_gps():

    global g_latitude, g_longitude
    gps_input= UART(1,baudrate=9600, tx=Pin(4), rx=Pin(5))
    print(gps_input)

    FIX_STATUS = False

    #Store GPS Coordinates
    latitude = None
    longitude = None
    satellites = None
    gpsTime = None

    #Function to convert raw Latitude and Longitude to actual Latitude and Longitude
    def convertToDegree(RawDegrees):

        RawAsFloat = float(RawDegrees)
        firstdigits = int(RawAsFloat/100) #degrees
        nexttwodigits = RawAsFloat - float(firstdigits*100) #minutes
        
        Converted = float(firstdigits + nexttwodigits/60.0)
        Converted = '{0:.6f}'.format(Converted) # to 6 decimal places
        #return str(Converted)
        return Converted

    while True:
        while FIX_STATUS == False:
            print("Waiting for GPS data")
            while True:
                buff = str(gps_input.readline())
                if buff is not None :
                    break
            parts = buff.split(',')
            #print(buff)
            if (parts[0] == "b'$GPGGA" and len(parts) == 15 and parts[1] and parts[2] and parts[3] and parts[4] and parts[5] and parts[6] and parts[7]):
                #print("Message ID  : " + parts[0])
                #print("UTC time    : " + parts[1])
                #print("Latitude    : " + parts[2])
                #print("N/S         : " + parts[3])
                #print("Longitude   : " + parts[4])
                #print("E/W         : " + parts[5])
                #print("Position Fix: " + parts[6])
                #print("n sat       : " + parts[7])
                latitude = convertToDegree(parts[2])
                if (parts[3] == 'S'):
                    latitude = -float(latitude)
                longitude = convertToDegree(parts[4])
                if (parts[5] == 'W'):
                    longitude = -float(longitude)
                satellites = parts[7]
                gpsTime = parts[1][0:2] + ":" + parts[1][2:4] + ":" + parts[1][4:6]
                if (parts[6] == '1'):
                    print(latitude)
                    print(longitude)
                    print(satellites)
                    print(gpsTime)
                    g_latitude = latitude
                    g_longitude = longitude
                    FIX_STATUS = True
                else:
                    print('No GPS fix')
            await asyncio.sleep_ms(250)
        await asyncio.sleep_ms(250)


# ---------------- Async:Serial Data from/to Stellarium ------------------
async def readwrite_stellarium():

    stellarium_uart = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1))
    stellarium_uart.init(bits=8, parity=None, stop=1)
    print(stellarium_uart)
    RA = '19:50:57#'
    DEC = '-25"58:14#'
    LX200_command = None

    while True:
        if stellarium_uart.any(): 
            LX200_command = stellarium_uart.read()
            print(LX200_command)
            try:                
                if LX200_command == b'#:GR#':
                    print(RA)
                    stellarium_uart.write(RA)
                elif LX200_command == b"#:GD#":
                    print(DEC)
                    stellarium_uart.write(DEC)
                else:
                    pass
            except:
                pass
        await asyncio.sleep_ms(250)


# ---------------- Main Program Loop ------------------
async def main():
    asyncio.create_task(read_gps())
    asyncio.create_task(readwrite_stellarium())
    
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


