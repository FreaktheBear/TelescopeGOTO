import asyncio
import binascii
import os
import math
import utime, time
from machine import I2C, SoftI2C, Pin, UART, ADC, RTC
from MPU import MPU6050
from ssd1306 import SSD1306_I2C
from stepper import Stepper


# ---------------- Global Variable Declaration ------------------
g_my_latitude = 0.0
g_my_longitude = 0.0
g_my_altitude = 0.0
g_gps_fix = False
g_sid_day = 23.934472222
g_lst = 0.0
g_lst_hms = (0, 0, 0)
g_lst_int = 0
g_lha_hms = (0, 0, 0)
g_alt_correction = 0.0
g_pitch = 0
g_roll = 0
g_alt_corrected = False
g_scope_current = False
g_scope_sync = False
g_scope_slew = False
g_precise_ra_dec = '00000000,00000000#'
g_ra_int = 0                            # 0 hours in integer format
g_dec_int = 3221225472                  # 270 degrees in integer format
g_joy_right = False
g_joy_left = False
g_joy_up = False
g_joy_down = False
g_joy_button = False

ms12_pin_RA = Pin(6, Pin.OUT, value=1)                  # Defines Pin MS1_2 as step 1/8 pins for motor 1 (RA)
ms12_pin_DEC = Pin(8, Pin.OUT, value=1)                 # Defines Pin MS1_2 as step 1/8 pins for motor 2 (DEC)

# ---------------- Async: Read Serial Data from NEO-7M GPS ------------------
async def read_gpsrmc():

    global g_my_latitude, g_my_longitude, g_my_altitude, g_gps_fix
    gps_input= UART(1,baudrate=9600, tx=Pin(4), rx=Pin(5))
    print(gps_input)

    FIX_STATUS = False
    buff = ''
    latitude = 0.0
    longitude = 0.0

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
            parts = buff.split(",")
            print(buff)
            if (parts[0] == "b'$GPRMC" and len(parts) > 9 and parts[1] and parts[2] and parts[3] and parts[4] and parts[5] and parts[6] and parts[9]):
                print("Message ID  : " + parts[0])
                print("UTC time    : " + parts[1])
                print("Pos. Status : " + parts[2])
                print("Latitude    : " + parts[3])
                print("N/S         : " + parts[4])
                print("Longitude   : " + parts[5])
                print("E/W         : " + parts[6])
                if (parts[2] == 'A'):                    # Test if GPS data is valid
                    latitude = convertToDegree(parts[3])
                    if (parts[4] == 'S'):
                        latitude = -float(latitude)
                    else:
                        latitude = float(latitude)
                    longitude = convertToDegree(parts[5])
                    if (parts[6] == 'W'):
                        longitude = -float(longitude)
                    else:
                        longitude = float(longitude)
                    print(latitude)
                    print(longitude)
                    g_my_latitude = latitude
                    g_my_longitude = longitude
                    FIX_STATUS = True
                    g_gps_fix = True

                    year = int('20'+parts[9][4:6])      # create RTC set datetime variables
                    month = int(parts[9][2:4])
                    day = int(parts[9][0:2])
                    hours = int(parts[1][0:2])
                    minutes = int(parts[1][2:4])
                    seconds = int(parts[1][4:6])
                    t_datetime = (year, month, day, 0, hours, minutes, seconds, 0)  #(year, month, day, weekday, hours, minutes, seconds, subseconds)
                    rtc = RTC()
                    rtc.datetime(t_datetime)
                    now = rtc.datetime()
                    print(now)
                    break
                else:
                    print('No GPS fix')

            
            await asyncio.sleep(0.1)
        await asyncio.sleep(0.01)


# ---------------- Async: Calculate Local Sidereal Time ------------------

async def calculate_lst():
    # Adopted from https://www.nies.ch/doc/astro/sternzeit.en.php

    global g_lst, g_lst_hms, g_lst_int

    def julian_date(year, month, day, utc=0):
        """
        Returns the Julian date, number of days since 1 January 4713 BC 12:00.
        utc is UTC in decimal hours. If utc=0, returns the date at 12:00 UTC.
        """
        if month > 2:
            y = year
            m = month
        else:
            y = year - 1
            m = month + 12
        d = day
        h = utc/24
        if year <= 1582 and month <= 10 and day <= 4:
            # Julian calendar
            b = 0
        elif year == 1582 and month == 10 and day > 4 and day < 15:
            # Gregorian calendar reform: 10 days (5 to 14 October 1582) were skipped.
            # In 1582 after 4 October follows the 15 October.
            d = 15
            b = -10
        else:
            # Gregorian Calendar
            a = int(y/100)
            b = 2 - a + int(a/4)
        jd = int(365.25*(y+4716)) + int(30.6001*(m+1)) + d + h + b - 1524.5
        return(jd)


    def siderial_time(year, month, day, utc=0, long=0):
        """
        Returns the siderial time in decimal hours. Longitude (long) is in 
        decimal degrees. If long=0, return value is Greenwich Mean Siderial Time 
        (GMST).
        """
        jd = julian_date(year, month, day)
        t = (jd - 2451545.0)/36525
        # Greenwich siderial time at 0h UTC (hours)
        st = (24110.54841 + 8640184.812866 * t +
            0.093104 * t**2 - 0.0000062 * t**3) / 3600
        # Greenwich siderial time at given UTC
        st = st + 1.00273790935*utc
        # Local siderial time at given UTC (longitude in degrees)
        st = st + long/15
        st = st % 24
        return(st)

    rtc = RTC()

    while True:
        now = rtc.datetime()
        year = now[0]
        month = now[1]
        day = now[2]
        utc = now[4] + now[5]/60 + now[6]/3600

        #long = 8.5
        long = g_my_longitude

        jd = julian_date(year, month, day)
        jd_utc = julian_date(year, month, day, utc)
        gmst = siderial_time(year, month, day, utc, 0)
        lmst = siderial_time(year, month, day, utc, long)
        lmst_h = int(lmst)
        lmst_m = int((lmst - lmst_h)*60)
        lmst_s = int((lmst - lmst_h - lmst_m/60)*3600)
        lmst_hms = (lmst_h, lmst_m, lmst_s)

        g_lst = lmst
        #g_lst_deg = lmst * 15 + 23.934472222/24 * 15
        g_lst_hms = lmst_hms
        g_lst_int = int(round((lmst/24) * 2**32))

        #print("My Longitude                       : ", long)
        #print("Current date                       : ", year, month, day)
        #print("Universal Time (UTC)               : ", utc)
        #print("Julian Date (0h UTC)               : ", jd)
        #print("Julian Date + UTC                  : ", jd_utc)
        #print("Greenwich Mean Siderial Time (GMST): ", gmst)
        #print("Local Mean Siderial Time (LMST)    : ", lmst)
        
        await asyncio.sleep(0.001)


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
            #print("pitch", pitch)
        elif g_alt_corrected == True:
            break
        await asyncio.sleep(0.0001)        


# ---------------- Async: Set Altitude Correction ------------------
async def alt_correction():
    global g_alt_correction, g_alt_corrected
    #pushbutton = Pin(6, Pin.IN, Pin.PULL_UP)    # GPIO6 Digital Input IX0.0
    
    while True:
        alt_correction =  -1*g_pitch + g_my_latitude
        g_alt_correction = alt_correction
        print("alt_correction", alt_correction)
        if alt_correction > 0 and g_alt_corrected == False or g_joy_button == True:
            g_alt_corrected = True
            break
        else:
            print("g_alt_corrected", g_alt_corrected)
            pass
        await asyncio.sleep(0.1)


# ---------------- Async: Joystick Control ------------------
async def joystick():
    global g_joy_right, g_joy_left, g_joy_up, g_joy_down, g_joy_button
    xAxis = ADC(Pin(26))
    yAxis = ADC(Pin(27))
    button = Pin(18,Pin.IN, Pin.PULL_UP)

    while True:
        xValue = xAxis.read_u16()
        #print("xValue", xValue)
        yValue = yAxis.read_u16()
        #print("yValue", yValue)
        buttonValue = button.value()
        if xValue >= 60000:
            xStatus = "down"
            g_joy_down = True
            g_joy_up = False
        elif xValue <= 600:
            xStatus = "up"
            g_joy_up = True
            g_joy_down = False
        elif yValue <= 600:
            yStatus = "right"
            g_joy_right = True
            g_joy_left = False
        elif yValue >= 60000:
            yStatus = "left"
            g_joy_left = True
            g_joy_right = False
        elif buttonValue == 0:
            buttonStatus = "pressed"
            g_joy_button = True
        else:
            xStatus = "middle"
            yStatus = "middle"
            g_joy_left = False
            g_joy_right = False
            g_joy_up = False
            g_joy_down = False
            buttonStatus = "not pressed"
            g_joy_button = False
        #print("X: " + xStatus + ", Y: " + yStatus + " -- button " + buttonStatus)
        await asyncio.sleep(0.1)

# ---------------- Async: GOTO possition ------------------
async def goto_position():
    global g_precise_ra_dec, g_lha_hms

    ra_int_old = g_ra_int
    ra_int_new = g_ra_int
    lha_int_old = 0
    lha_int_new = 0
    lha_int_12h = 2**32/2
    lha_abs_old = 0
    lha_abs_new = 0
    dec_int_180 = 2**32/2
    dec_int_old = g_dec_int

    counts = 0.0
    sid_sec_cnt = 928                 # Steps per sidereal day second = (1/23.934472222 * 8000)/3600 = 0.928460933
    utc_offset = False
    utc_rasteps = 0

    step_pin_ra = 11
    dir_pin_ra = 10
    stepper_ra = Stepper(dir_pin_ra, step_pin_ra)

    step_pin_dec = 15
    dir_pin_dec = 14
    stepper_dec = Stepper(dir_pin_dec, step_pin_dec)

            
    def lha_abs_calc(int_lha):

        if int_lha < 0:
            int_lha_abs = int_lha + 2**32
            return int_lha_abs
        elif int_lha > 0:
            int_lha_abs = int_lha
            return int_lha_abs
        else:
            int_lha_abs = 0
            return int_lha_abs
    

    def lha_hms_calc(lha_abs):

        lha_h = int(lha_abs/2**32 * 24)
        lha_m = int((lha_abs/2**32 * 24 - lha_h)*60)
        lha_s = int((lha_abs/2**32 * 24 - lha_h - lha_m/60)*3600)
        lha_hms = (lha_h, lha_m, lha_s)
        return lha_hms


    def ra_steps_calc(lha_old_abs, lha_new_abs):

        if lha_int_12h < lha_new_abs < 2**32 and lha_old_abs == 0:
            steps = round((2**32 - lha_new_abs)/2**32 * 8000)
            return steps
        elif lha_int_12h < lha_new_abs < 2**32 and lha_int_12h < lha_old_abs < 2**32 and lha_abs_old != 0:
            if lha_abs_new > lha_abs_old:
                steps = -round((lha_abs_new - lha_abs_old)/2**32 * 8000)
                return steps
            elif lha_new_abs <= lha_abs_old:
                steps = round((lha_abs_old - lha_abs_new)/2**32 * 8000)
                return steps
        elif 0 < lha_new_abs < lha_int_12h and lha_old_abs == 0:
            steps = -round(lha_new_abs/2**32 * 8000)
            return steps
        else:
            steps = 0
            return steps


    def dec_steps_calc(lha_new_abs, lha_old_abs, int_old_dec, int_new_dec):

        if lha_int_12h < lha_new_abs < 2**32 and lha_int_12h < lha_old_abs < 2**32:
            if dec_int_180 < int_old_dec < 2**32 and dec_int_180 < int_new_dec < 2**32 and int_new_dec > int_old_dec:
                steps = -round((int_new_dec - int_old_dec)/2**32 * 8000)
                return steps
            elif dec_int_180 < int_old_dec < 2**32 and dec_int_180 < int_new_dec < 2**32 and int_new_dec <= int_old_dec:
                steps = round((int_old_dec - int_new_dec)/2**32 * 8000)
                return steps
            elif dec_int_180 < int_old_dec < 2**32 and 0 < int_new_dec < dec_int_180:
                steps = -round((2**32 - int_old_dec + int_new_dec)/2**32 * 8000)
                return steps
            elif dec_int_180 < int_new_dec < 2**32 and 0 < int_old_dec < dec_int_180:
                steps = round((2**32 - int_new_dec + int_old_dec)/2**32 * 8000)
                return steps
            else:
                steps = 0
                return steps
        elif 0 < lha_new_abs < lha_int_12h:
            if int_new_dec > int_old_dec:
                steps = round((int_new_dec - int_old_dec)/2**32 * 8000)
                return steps
            elif int_new_dec <= int_old_dec:
                steps = -round((int_old_dec - int_new_dec)/2**32 * 8000)
                return steps
            else:
                steps = 0
                return steps
            

    while True:
        if g_alt_corrected == True and g_scope_current == True and g_scope_sync == False and g_scope_slew == False:
            counts += 1
            if counts >= sid_sec_cnt:                    
                stepper_ra.move(1, 8000, 1)
                counts = 0
            if g_joy_left == True:
                stepper_ra.move(-1, 8000, 1)
            elif g_joy_right == True:
                stepper_ra.move(1, 8000, 1)
            elif g_joy_up == True:
                stepper_dec.move(-1, 8000, 1)
            elif g_joy_down == True:
                stepper_dec.move(1, 8000, 1)
            lha_int_old = g_lst_int - ra_int_old
            lha_abs_old = lha_abs_calc(lha_int_old)
            g_lha_hms = lha_hms_calc(lha_abs_old)
            ra_hex = hex(ra_int_old)
            ra_hex = ra_hex[2:]
            ra_hex = ('00000000' + ra_hex)[-8:]                                             # Add leading zeros
            dec_hex = hex(dec_int_old)
            dec_hex = dec_hex[2:]
            dec_hex = ('00000000' + dec_hex)[-8:]
            g_precise_ra_dec = str.upper(ra_hex + ',' + dec_hex + '#')
        elif g_scope_slew == True:
            if ra_int_old == 0:
                ra_int_old = g_lst_int
            lha_int_old = g_lst_int - ra_int_old
            lha_abs_old = lha_abs_calc(lha_int_old)
            print("lha_abs_old", lha_abs_old)
            ra_int_new = g_ra_int
            lha_int_new = g_lst_int - ra_int_new
            lha_abs_new = lha_abs_calc(lha_int_new)
            print("lha_abs_new", lha_abs_new)
            g_lha_hms = lha_hms_calc(lha_abs_new)
            ra_steps = ra_steps_calc(lha_abs_old, lha_abs_new)
            print("ra_steps", ra_steps)
            stepper_ra.move(ra_steps, 8000, 2)
            ra_int_old = ra_int_new
            lha_abs_old = lha_abs_new
            ra_hex = hex(ra_int_old)
            ra_hex = ra_hex[2:]
            ra_hex = ('00000000' + ra_hex)[-8:]
            dec_int_new = g_dec_int
            dec_steps = dec_steps_calc(lha_abs_new, lha_abs_old, dec_int_old, dec_int_new)
            print("dec_steps", dec_steps)
            stepper_dec.move(dec_steps, 8000, 2)
            dec_int_old = dec_int_new
            dec_hex = hex(dec_int_new)
            dec_hex = dec_hex[2:]
            dec_hex = ('00000000' + dec_hex)[-8:]
            g_precise_ra_dec = str.upper(ra_hex + ',' + dec_hex + '#')
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
        else:
            pass
        await asyncio.sleep(0.01)


# ---------------- Async: OLED Readout ------------------

async def oled():
    WIDTH  = 128                                            # oled display width
    HEIGHT = 64                                             # oled display height

    # Pin assignment 
    i2c = SoftI2C(scl=Pin(3), sda=Pin(2))

    oled = SSD1306_I2C(WIDTH, HEIGHT, i2c)          # Init oled display

    while True:
        if g_alt_corrected == False:
            # Clear the display
            oled.fill(0)
            # text, x-position, y-position
            oled.text("Alt. correction:", 0, 0)
            str_alt_correction = str(round(g_alt_correction, 2))
            oled.text(str_alt_correction, 0, 15)
            # Show the updated display
            oled.show()
        else:
            # Clear the display
            oled.fill(0)
            # text, x-position, y-position
            oled.text("Right ascension:", 0, 0)
            ra_deg = (g_ra_int/2**32)*24
            ra_decimal , ra_hours = math.modf(ra_deg)
            ra_hour_str = str('%02d' %ra_hours)
            ra_minsec = ra_decimal*60
            ra_seconds, ra_min = math.modf(ra_minsec)
            ra_min_str = str('%02d' %ra_min)
            ra_sec = ra_seconds*60
            ra_sec_str = str(round(ra_sec, 2))
            str_ra = (ra_hour_str+'h'+ra_min_str+'m'+ra_sec_str+'s')
            oled.text(str_ra, 0, 15)
            oled.text("Declination:", 0, 30)
            dec_deg = (g_dec_int/2**32)*360
            if dec_deg >= 180:
                dec_deg = dec_deg - 360
                #print("dec_deg", dec_deg)
            dec_decimal, dec_degrees = math.modf(dec_deg)
            dec_degrees_str = str('%03d' %dec_degrees)
            dec_minsec = abs(dec_decimal*60)
            dec_seconds, dec_min = math.modf(dec_minsec)
            dec_min_str = str('%02d' %dec_min)
            dec_sec = dec_seconds*60
            dec_sec_str = str(round(dec_sec, 2))
            str_dec = (dec_degrees_str+'deg'+dec_min_str+'m'+dec_sec_str+'s')
            oled.text(str_dec, 0, 45)
            # Show the updated display
            oled.show()            
        await asyncio.sleep(0.2)            


# ---------------- Async: Serial Data from/to Stellarium ------------------
async def readwrite_stellarium():
    global g_scope_current, g_scope_sync, g_scope_slew, g_ra_int, g_dec_int
    stellarium_uart = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1))
    stellarium_uart.init(bits=8, parity=None, stop=1)
    print(stellarium_uart)
    #LX200 format does not work for micropython due to special character used
    #NexStar format
    #'00000000,C0000000#' #Equatorial South Pole coordinates 0 hours, 270 (-90) degrees in Nexstar values equals, hex capital letters needed!

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
                    ra_int = int((msg[1:9]), 16) # take chr1_9 hex numbers and convert to int
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
    asyncio.create_task(read_gpsrmc())
    asyncio.create_task(calculate_lst())
    asyncio.create_task(read_pitchroll())
    asyncio.create_task(alt_correction())
    asyncio.create_task(joystick())
    asyncio.create_task(goto_position())
    asyncio.create_task(oled())
    asyncio.create_task(readwrite_stellarium())
    
    while True:
        try:
            if True:
                print("Main program running, LSTime, LHATime: ", g_lst_hms, g_lha_hms)
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


"""async def read_gps():

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
                if (parts[6] == '1' or parts[6] == '2'):
                    latitude = convertToDegree(parts[2])
                    if (parts[3] == 'S'):
                        latitude = -float(latitude)
                    else:
                        latitude = float(latitude)
                    longitude = convertToDegree(parts[4])
                    if (parts[5] == 'W'):
                        longitude = -float(longitude)
                    else:
                        longitude = float(longitude)
                    satellites = parts[7]
                    gpsTime = parts[1][0:2] + ":" + parts[1][2:4] + ":" + parts[1][4:6]
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
        await asynciolha_h = int(lha_abs_old/2**32 * 24)
            lha_m = int((lha_abs_old/2**32 * 24 - lha_h)*60)
            lha_s = int((lha_abs_old/2**32 * 24 - lha_h - lha_m/60)*3600)("ra_int_new", ra_int_new)
            elif utc_offset == False and utc_rasteps >= 2**32/2:
                utc_rasteps = calc_steps_utc()
                ra_int_new = g_ra_int + (2**32/2 - utc_rasteps)
                utc_offset = True
                print("ra_int_new", ra_int_new)
            else:
                pass
            
            ra_deg_new = ra_int_new/2**32 * 360
            ra_deg_h = int(ra_deg_new/15)
            ra_deg_m = int((ra_deg_new/15 - ra_deg_h)*60)
            ra_deg_s = int((ra_deg_new/15 - ra_deg_h - ra_deg_m/60)*3600)
            ra_deg_hms = (ra_deg_h, ra_deg_m, ra_deg_s)
            print("ra_deg_hms", ra_deg_hms)

            lha_h = int(lha_abs_old/2**32 * 24)
            lha_m = int((lha_abs_old/2**32 * 24 - lha_h)*60)
            lha_s = int((lha_abs_old/2**32 * 24 - lha_h - lha_m/60)*3600)
            g_lha_hms = (lha_h, lha_m, lha_s)"""