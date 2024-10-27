import asyncio
import os
import machine
import math
import utime, time
from machine import I2C, Pin, UART
from math import sqrt, atan2, pi, copysign, sin, cos
#from mpu9250 import MPU9250


# ---------------- Variable Decleration ------------------ ��
g_my_latitude = 0.0
g_my_longitude = 0.0
g_my_altitude = 0.0
g_pot_ra = 0.0
g_pot_dec = 0.0
g_pot_alt = 0.0
g_pot_az = 0.0
g_scope_ra = None
g_scope_dec = None
g_scope_altitude = None
g_precise_RA_DEC = None


# ---------------- Async: Read Serial Data from NEO-7M GPS ------------------
async def read_gps():

    global g_my_latitude, g_my_longitude, g_my_altitude
    gps_input= UART(1,baudrate=9600, tx=Pin(4), rx=Pin(5))
    print(gps_input)

    FIX_STATUS = False

    #Store GPS Coordinates
    latitude = None
    longitude = None
    altitude = None
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
                print("Position Fix: " + parts[6])
                #print("n sat       : " + parts[7])
                latitude = convertToDegree(parts[2])
                if (parts[3] == 'S'):
                    latitude = -float(latitude)
                longitude = convertToDegree(parts[4])
                if (parts[5] == 'W'):
                    longitude = -float(longitude)
                satellites = parts[7]
                gpsTime = parts[1][0:2] + ":" + parts[1][2:4] + ":" + parts[1][4:6]
                if (parts[6] == '1' or parts[6] == '2'):
                    print(latitude)
                    print(longitude)
                    print(satellites)
                    print(gpsTime)
                    g_my_latitude = latitude
                    g_my_longitude = longitude

                    FIX_STATUS = True
                else:
                    print('No GPS fix')
            
            await asyncio.sleep_ms(250)
        await asyncio.sleep_ms(250)


# ---------------- Async: Read Data from IMU ------------------
async def read_pot_ra():

    global g_pot_ra
    Potmeter = 0.0
    confidence_val = 0.1
    POT = machine.ADC(26)  #setup analog reading on ADC

    while True:
            Potmeter = confidence_val*POT.read_u16()+(1-confidence_val)*Potmeter
            g_pot_ra = Potmeter
            #print("Right Ascension:", Potmeter)
            await asyncio.sleep(0.05)        


async def read_pot_dec():

    global g_pot_dec
    Potmeter = 0.0
    confidence_val = 0.1
    POT = machine.ADC(27)  #setup analog reading on ADC

    while True:
            Potmeter = confidence_val*POT.read_u16()+(1-confidence_val)*Potmeter
            g_pot_dec = Potmeter
            #print("Declination:", Potmeter)
            await asyncio.sleep(0.05) 
        

async def read_imu():

    global g_scope_ra, g_scope_dec, g_precise_RA_DEC

    while True:
        #print(int(g_pot_ra))
        right_ascension_hex = ('%06s' % (hex(int(g_pot_ra*100))[2:])) # add precision by multiplying with 100 and cut off 0x
        #print(int(g_pot_dec))
        declination_hex = ('%06s' % (hex(int(g_pot_dec*100))[2:])) # add precision by multiplying with 100 and cut off 0x
        #print("RA_DEC: ", right_ascension_hex, declination_hex)
        g_precise_RA_DEC = str(right_ascension_hex+'00'+','+declination_hex+'00'+'#')
        """ra_hours, ra_minsec = divmod(g_pot_ra, 1)
        ra_hour_str = str('%02d' % int(ra_hours))
        ra_decimal = ra_minsec*60
        ra_min, ra_seconds = divmod(ra_decimal, 1)
        ra_min_str = str('%02d' % int(ra_min))
        ra_sec = ra_seconds*60
        ra_sec_str = str('%02d' % int(ra_sec))
        g_scope_ra = ('#'+ra_hour_str+':'+ra_min_str+':'+ra_sec_str+'#')

        dec_degrees, dec_minsec = divmod(g_pot_dec, 1)
        if g_my_latitude < 0:
            dec_degrees = -1*dec_degrees
        else:
            dec_degrees = dec_degrees
        dec_degrees_str = str('%03d' % int(dec_degrees))
        dec_decimal = dec_minsec*60
        dec_min, dec_seconds = divmod(dec_decimal, 1)
        dec_min_str = str('%02d' % int(dec_min))
        dec_sec = dec_seconds*60
        dec_sec_str = str('%02d' % int(dec_sec))

        g_scope_dec = ('#'+dec_degrees_str+'*'+dec_min_str+':'+dec_sec_str+'#')"""
        await asyncio.sleep(0.1)

    """global g_scope_altitude, g_precise_RA_DEC
    MPU = 0x68
    id = 0
    sda = Pin(20)
    scl = Pin(21)

    #i2c = I2C(sda=Pin(20), scl=Pin(21), freq=400000)
    i2c = I2C(id=id, scl=scl, sda=sda, freq=400000)    
    print(i2c.scan())
    mpu = MPU9250(i2c)

    # Calibration and bias offset
    mpu.ak8963.calibrate(count=200)
    pitch_bias = 0.0
    roll_bias = 0.0

    # For low pass filtering
    #filtered_x_value = 0.0 
    #filtered_y_value = 0.0

    Atan = 0
    Confidence_Val = 0.1

    while True:
        xAccel = mpu.accel.x
        if xAccel > 1:
            xAccel = 1
        elif xAccel < -1:
            xAccel = -1
        yAccel = mpu.accel.y
        if yAccel > 1:
            yAccel = 1
        elif yAccel < -1:
            yAccel = -1
        zAccel = mpu.accel.z
        if zAccel > 1:
            zAccel = 1
        elif zAccel < -1:
            zAccel = -1
        xRad = math.acos(xAccel)
        xDeg = xRad/(2*math.pi)*360
        yRad = math.acos(yAccel)
        yDeg = yRad/(2*math.pi)*360
        zRad = math.asin(zAccel)
        zDeg = zRad/(2*math.pi)*360
        Atan = Confidence_Val*math.atan2(zAccel,yAccel)+(1-Confidence_Val)*Atan
        #Dec = math.asin(math.sin(g_my_latitude/360*2*math.pi)*math.sin(Atan)+math.cos((g_my_latitude/360*2*math.pi))*math.cos(Atan)*math.cos(math.pi))
        #declination = int(Dec/(2*math.pi)*65536)
        
        if declination < 0:
            declination = 0
        else:
            pass
        if g_my_latitude < 0: # Correction for Southern hemisphere
            declination = declination+32768
        else:
            pass
        #hex_declination = ('%06s' % (hex(declination*100)[2:])) # add precision by multiplying with 100 and cut off 0x
        #print("declination: ",declination, hex_declination)
        #g_precise_RA_DEC = ('34AB0500'+','+hex_declination+'00#') 
        await asyncio.sleep_ms(50)"""

# ---------------- Async: Serial Data from/to Stellarium ------------------
async def readwrite_stellarium():

    stellarium_uart = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1))
    stellarium_uart.init(bits=8, parity=None, stop=1)
    print(stellarium_uart)
    #LX200 format does not work for micropython due to special character used
    #RA = '19:50:57'
    #DEC = '-25:50:14'
    #RA = '19:50:57#'
    #DEC = '-25*58:14'
    #DEC = '-25ß58:14'


    #NexStar format
    #e = '34AB0500,12CE0500#'
    LX200_command = None

    while True:
        if stellarium_uart.any(): 
            LX200_command = stellarium_uart.read()
            print(LX200_command)
            """try:                
                if LX200_command == b'#:GR#':
                    print(g_scope_ra)
                    stellarium_uart.write(g_scope_ra)
                elif LX200_command == b'#:GD#':
                    print(g_scope_dec)
                    stellarium_uart.write(g_scope_dec)"""
            try:
                if LX200_command == b'e':
                    print(g_precise_RA_DEC)
                    stellarium_uart.write(g_precise_RA_DEC)    
                else:
                    pass
            except:
                pass
        await asyncio.sleep_ms(250)


# ---------------- Main Program Loop ------------------
async def main():
    asyncio.create_task(read_gps())
    asyncio.create_task(read_pot_ra())
    asyncio.create_task(read_pot_dec())
    asyncio.create_task(read_imu())
    asyncio.create_task(readwrite_stellarium())
    
    while True:
        try:
            if True:
                #print("Main program running")
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


