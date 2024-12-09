import asyncio
import binascii
import os
import machine
import math
import utime, time
import ssd1306
import stepper_controller as ctrl
from machine import I2C, Pin, UART
from MPU import MPU6050


# ---------------- Global Variable Declaration ------------------ ��
g_my_latitude = 0.0
g_my_longitude = 0.0
g_my_altitude = 0.0
g_alt_correction = 0.0
g_pitch = 0
g_roll = 0
g_sidereal_steps = 0
g_alt_corrected = False
g_scope_current = False
g_scope_sync = False
g_scope_slew = False
g_precise_ra_dec = '00000000,00000000#'
g_ra_int = 0
g_dec_int = 3221225472


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
                    longitude = float(longitude)
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
            
            await asyncio.sleep(0.25)
        await asyncio.sleep(0.25)


# ---------------- Async: Read Right Ascension and Declination Data from IMU ------------------
async def read_pitchroll():

    global g_pitch, g_roll

    obj = MPU6050(0,20,21)  
    obj.callibrate_gyro() #calibrate gyro 
    obj.callibrate_acc() #calibrating accelerometer
    
    while True:
        if g_alt_corrected == False:
            pitch, roll, dt = obj.return_angles()
            g_pitch = pitch
            g_roll = roll
        elif g_alt_corrected == True:
            break
        await asyncio.sleep(0.0001)        


# ---------------- Async: Set Altitude Correction ------------------
async def alt_correction():
    global g_alt_correction, g_alt_corrected
    pushbutton = Pin(6, Pin.IN, Pin.PULL_UP)    # GPIO6 Digital Input IX0.0
    
    while True:    
        alt_correction =  -1*g_pitch + g_my_latitude
        g_alt_correction = alt_correction
        print("alt_correction", alt_correction)
        if alt_correction > 0 and g_alt_corrected == False or pushbutton.value() != 1:
            pushbutton.value(1)
            g_alt_corrected = True
            break
        else:
            pass
        await asyncio.sleep(0.1)

# ---------------- Async: GOTO possition ------------------
async def goto_position():
    global g_precise_ra_dec

    ra_int_old = g_ra_int
    dec_int_old = g_dec_int
    counts = 0.0

    def calc_steps(int_old, int_new):
        if int_new > int_old:
            steps = round((int_new - int_old)/2**32 * 31800)               # full rev = 200 * 16 * 9.9375 = 31800
            return steps
        elif int_new < int_old:
            steps = round(-(int_old - int_new)/2**32 * 31800)
            return steps
        else:
            pass

    while True:
        if g_alt_corrected == True and g_scope_current == True and g_scope_sync == False and g_scope_slew == False:
            counts += 0.1
            if counts >= 88.3:  # initial calculations 1 step per 8.8333 sec, but imperically adjusted
                ctrl.steps(-10, 0) #ra_int_old = ra_int_old - 1350618 # 1 step = 2^32/31800 = 135061.8 bits
                counts = 0.0
            ra_hex = hex(ra_int_old)
            ra_hex = ra_hex[2:]
            ra_hex = ('00000000' + ra_hex)[-8:]
            dec_hex = hex(dec_int_old)
            dec_hex = dec_hex[2:]
            dec_hex = ('00000000' + dec_hex)[-8:]
            g_precise_ra_dec = str.upper(ra_hex + ',' + dec_hex + '#')
            print("precise ra dec: ", g_precise_ra_dec, counts)
        elif g_scope_sync == True:
            ra_int_old = g_ra_int
            dec_int_old = g_dec_int
            ra_hex = hex(ra_int_old)
            ra_hex = ra_hex[2:]
            ra_hex = ('00000000' + ra_hex)[-8:]
            dec_hex = hex(dec_int_old)
            dec_hex = dec_hex[2:]
            dec_hex = ('00000000' + dec_hex)[-8:]
            g_precise_ra_dec = str.upper(ra_hex + ',' + dec_hex + '#')
        elif g_scope_slew == True:
            ra_int_new = g_ra_int
            ra_steps = calc_steps(ra_int_old, ra_int_new)
            dec_int_new = g_dec_int
            dec_steps = calc_steps(dec_int_old, dec_int_new)
            ctrl.steps(ra_steps, dec_steps)
            ra_int_old = ra_int_new
            dec_int_old = dec_int_new
            ra_hex = hex(ra_int_new)
            ra_hex = ra_hex[2:]
            ra_hex = ('00000000' + ra_hex)[-8:]
            dec_hex = hex(dec_int_new)
            dec_hex = dec_hex[2:]
            dec_hex = ('00000000' + dec_hex)[-8:]
            g_precise_ra_dec = str.upper(ra_hex + ',' + dec_hex + '#')
        else:
            pass
        await asyncio.sleep(0.1)


# ---------------- Async: OLED Readout ------------------
"""async def oled():
    # using default address 0x3C
    i2c = I2C(sda=Pin(2), scl=Pin(3))
    dsp = ssd1306.SSD1306_I2C(128, 64, i2c)
    dsp.fill(0)

    while True:
        if g_alt_corrected == False:
            dsp.text('Alt correction',0,0)
            msg='Alt: '+str(round(g_alt_correction,2))
            dsp.text(msg,0,16)
            dsp.show()
            dsp.fill(0)
        elif g_alt_corrected == True:
            dsp.text('Celestial coordinates',0,0)
            msg='RA: '+g_precise_ra_dec
            dsp.text(msg,0,16)
            dsp.show()
            dsp.fill(0)            
        await asyncio.sleep(0.2)"""


# ---------------- Async: Serial Data from/to Stellarium ------------------
async def readwrite_stellarium():
    global g_scope_current, g_scope_sync, g_scope_slew, g_ra_int, g_dec_int
    stellarium_uart = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1))
    stellarium_uart.init(bits=8, parity=None, stop=1)
    print(stellarium_uart)

    #LX200 format does not work for micropython due to special character used
    #NexStar format
    #'00000000,C0000000#' #Equatorial South Pole coordinates 0 hours, 270 degrees in Nexstar values, hex capital letters needed!

    NextStar_cmd = None
    NextStar_cmdchr0 = None

    while True:
        precise_ra_dec = g_precise_ra_dec
        if stellarium_uart.any(): 
            NextStar_cmd = stellarium_uart.read()
            NextStar_cmdchr0 = chr(NextStar_cmd[0])
            print(NextStar_cmd)
            try:
                if NextStar_cmdchr0 == 'e':
                    g_scope_current = True
                    g_scope_sync = False
                    g_scope_slew = False             
                    msg = str(NextStar_cmd, 'utf-8')
                    stellarium_uart.write(precise_ra_dec)
                elif NextStar_cmdchr0 == 's':
                    g_scope_sync = True
                    g_scope_current = False
                    g_scope_slew = False
                    msg = str(NextStar_cmd, 'utf-8')
                    ra_int = int((msg[1:9]), 16) # take chr1_8 hex numbers and convert to int
                    dec_int = int((msg[10:18]), 16) # take chr10_18 hex numbers and convert to int
                    g_ra_int = ra_int
                    g_dec_int = dec_int
                    stellarium_uart.write(precise_ra_dec)
                elif NextStar_cmdchr0 == 'r':
                    g_scope_slew = True
                    g_scope_current = False
                    g_scope_sync = False
                    msg = str(NextStar_cmd, 'utf-8')
                    ra_int = int((msg[1:9]), 16) # take chr1_9 hex numbers and convert to int
                    dec_int = int((msg[10:18]), 16) # take chr11_18 hex numbers and convert to int
                    g_ra_int = ra_int
                    g_dec_int = dec_int
                    stellarium_uart.write(precise_ra_dec)                
                else:
                    pass
            except:
                pass
        await asyncio.sleep(0.25)


# ---------------- Main Program Loop ------------------
async def main():
    asyncio.create_task(read_gps())
    asyncio.create_task(read_pitchroll())
    asyncio.create_task(alt_correction())
    asyncio.create_task(goto_position())
    #asyncio.create_task(oled())
    asyncio.create_task(readwrite_stellarium())
    
    while True:
        try:
            if True:
                #print("Main program running")
                await asyncio.sleep(1)   # Sleep for 1 seconds
        except OSError as e:
            print('Main error')
        await asyncio.sleep(0.1)   # Sleep for 0.1 seconds

try:
    asyncio.run(main())  # Run the main asynchronous function
except OSError as e:
    print('Runtime error')
finally:
    asyncio.new_event_loop() #Create a new event loop


