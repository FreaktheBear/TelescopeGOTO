import asyncio
import binascii
import os
import machine
import math
import utime, time
from machine import I2C, Pin, UART
from imu import MPU6050
from stepper import Stepper
#from mpu9250 import MPU9250


# ---------------- Global Variable Declaration ------------------ ��
g_my_latitude = 0.0
g_my_longitude = 0.0
g_my_altitude = 0.0
g_ra_init = 0
g_dec_init = 0
g_init_finished = False
#g_rightascension = 0.0
#g_declination = 0.0
g_scope_RA = 0.0
g_scope_DEC = 0.0
g_scope_init = False
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
            
            await asyncio.sleep(0.25)
        await asyncio.sleep(0.25)


# ---------------- Async: Read Right Ascension and Declination Data from IMU ------------------

async def read_radec():

    i2c = I2C(0, sda=Pin(20), scl=Pin(21), freq = 400000)
    mpu_ra = MPU6050(i2c, device_addr=0)
    mpu_dec  = MPU6050(i2c, device_addr=1)

    global g_ra_init, g_dec_init, g_precise_RA_DEC
    
    rightascensionComp=0
    declinationComp=0
    
    errorRA=0
    errorDEC=0
    
    tLoop=0
    
    while True:
        tStart=time.ticks_ms()

        yAccelRA= mpu_ra.accel.y
        zAccelRA= mpu_ra.accel.z
        yGyroRA= mpu_ra.gyro.y
        zGyroRA= mpu_ra.gyro.z
        
        rightascensionA= math.atan2(yAccelRA,zAccelRA)/2/math.pi*360 + 180
        rightascensionComp= rightascensionA*.30 + .70*(rightascensionComp+yGyroRA*tLoop)+errorRA*.01 
        errorRA=errorRA + (rightascensionA-rightascensionComp)*tLoop

        yAccelDEC= mpu_dec.accel.y
        zAccelDEC= mpu_dec.accel.z
        yGyroDEC= mpu_dec.gyro.y
        zGyroDEC= mpu_dec.gyro.z

        declinationA= math.atan2(yAccelDEC,zAccelDEC)/2/math.pi*360 + 180
        declinationComp= declinationA*.30 + .70*(declinationComp+yGyroDEC*tLoop)+errorDEC*.01 
        errorDEC=errorDEC + (declinationA-declinationComp)*tLoop

        ra_init = int(rightascensionComp/360*65536*100)            # *100 for adding extra precision
        dec_init = int((abs(360 - declinationComp))/360*65536*100) # *100 for adding extra precision

        ra_init_hex = hex(ra_init)
        ra_init_hex = ra_init_hex[2:] # strip 0x from string
        ra_init_hex = ('000000' + ra_init_hex)[-6:] # add leading zero's for 6 chars

        dec_init_hex = hex(dec_init)
        dec_init_hex = dec_init_hex[2:]
        dec_init_hex = ('000000' + dec_init_hex)[-6:]

        g_ra_init = ra_init
        g_dec_init = dec_init
        g_precise_RA_DEC = str.upper(ra_init_hex + '00' + ',' + dec_init_hex + '00' + '#')
        
        tStop= time.ticks_ms()
        tLoop= (tStop-tStart)*.001
        await asyncio.sleep(0.0001)        


# ---------------- Async: GOTO possition ------------------
async def goto_init():
    global g_init_finished
    motorRA = Stepper(0, 10, 11)
    step16RA = Pin(12, Pin.OUT, value=False)               # GPIO12 Digital Output

    zeropoint = int(((1/360)*65536)*100) # 1 degree = 18200
    slowdownplus = int((15/360*65536)*100)
    slowdownminus = int((345/360*65536))
    fullcircle = int(360*65536)


    speed_motRA = 0
    init_RA_clockwise = False
    init_RA_anticlockwise = False
    initstep1_RA = False
    initstep2_RA = False
    initstep3_RA = False
    initstep4_RA = False
    init_RA_finished = False

    motorDEC = Stepper(1, 14, 15)
    step16DEC = Pin(13, Pin.OUT, value=False)              # GPIO13 Digital Output

    speed_motDEC = 0
    init_DEC_clockwise = False
    init_DEC_anticlockwise = False
    initstep1_DEC = False
    initstep2_DEC = False
    initstep3_DEC = False
    initstep4_DEC = False
    init_DEC_finished = False

    # ------------------ RA Goto Init Position Clock Wise ------------------ #
    while True:
        rightascension = g_ra_init
        if rightascension > zeropoint and init_RA_anticlockwise == False and init_RA_finished == False:
            #print("rightascension", rightascension)
            init_RA_clockwise = True
            init_RA_anticlockwise = False
            if rightascension > slowdownplus and 0 <= speed_motRA < 20 and initstep2_RA == False and init_RA_clockwise == True:
                initstep1_RA = True
                step16RA.value(False)
                #print("initstep1_RA clockwise", initstep1_RA)
                speed_motRA = speed_motRA +5
                motorRA.set_steps_per_second(speed_motRA)
            elif rightascension > slowdownplus and speed_motRA >= 20 and initstep3_RA == False and init_RA_clockwise == True:
                initstep2_RA = True
                step16RA.value(False)
                #print("initstep2_RA clockwise", initstep2_RA)
                speed_motRA = 20
                motorRA.set_steps_per_second(speed_motRA)
            elif slowdownplus >= rightascension > zeropoint and speed_motRA >= 10 and initstep4_RA == False and init_RA_clockwise == True:
                initstep3_RA = True
                step16RA.value(False)
                #print("initstep3_RA clockwise", initstep3_RA)
                speed_motRA = speed_motRA -5
                motorRA.set_steps_per_second(speed_motRA)
            elif slowdownplus > rightascension > zeropoint and speed_motRA < 10 and init_RA_finished == False and init_RA_clockwise == True:
                initstep4_RA = True
                step16RA.value(True)
                #print("initstep4_RA clockwise", initstep4_RA)
                speed_motRA = 10
                motorRA.set_steps_per_second(speed_motRA)
        elif rightascension < zeropoint and init_RA_clockwise == True:
            init_RA_finished = True
            step16RA.value(False)
            speed_motRA = 0
            motorRA.set_steps_per_second(speed_motRA)
            #print("init_RA_finished clockwise", init_RA_finished)

        # ------------------ RA Goto Init Position Anti Clock Wise ------------------ #
        """if rightascension < zeropoint and init_RA_clockwise == False and init_RA_finished == False:
            init_RA_anticlockwise = True
            init_RA_clockwise = False
            if rightascension < slowdownminus and 0 >= speed_motRA > -50 and initstep2_RA == False and init_RA_anticlockwise == True:
                initstep1_RA = True
                step16RA.value(False)
                #print("initstep1_RA anticlockwise", initstep1_RA)
                speed_motRA = speed_motRA -5
                motorRA.set_steps_per_second(speed_motRA)
            elif rightascension < slowdownminus and speed_motRA <= -50 and initstep3_RA == False and init_RA_anticlockwise == True:
                initstep2_RA = True
                step16RA.value(False)
                #print("initstep2_RA anticlockwise", initstep2_RA)
                speed_motRA = -50
                motorRA.set_steps_per_second(speed_motRA)
            elif slowdownminus <= rightascension < 0 and speed_motRA <= -10 and initstep4_RA == False and init_RA_anticlockwise == True:
                initstep3_RA = True
                step16RA.value(False)
                #print("initstep3_RA anticlockwise", initstep3_RA)
                speed_motRA = speed_motRA +5
                motorRA.set_steps_per_second(speed_motRA)
            elif slowdownminus < rightascension < 0 and speed_motRA > -10 and init_RA_finished == False and init_RA_anticlockwise == True:
                initstep4_RA = True
                step16RA.value(True)
                #print("initstep4_RA anticlockwise", initstep4_RA)
                speed_motRA = -10
                motorRA.set_steps_per_second(speed_motRA)
        elif rightascension > zeropoint and init_RA_anticlockwise == True:
            init_RA_finished = True
            step16RA.value(False)
            speed_motRA = 0
            motorRA.set_steps_per_second(speed_motRA)
            #print("init_RA_finished anticlockwise", init_RA_finished)


    # ------------------ DEC Goto Init Position Clock Wise ------------------ #
        declination = g_dec_init
        if declination < zeropoint and init_DEC_anticlockwise == False and init_RA_finished == True and init_DEC_finished == False:
            init_DEC_clockwise = True
            init_DEC_anticlockwise = False
            if declination < slowdownminus and 0 <= speed_motDEC < 50 and initstep2_DEC == False and init_DEC_clockwise == True:
                initstep1_DEC = True
                step16DEC.value(False)
                #print("initstep1_DEC clockwise", initstep1_DEC)
                speed_motDEC = speed_motDEC +5
                motorDEC.set_steps_per_second(speed_motDEC)
            elif declination < slowdownminus and speed_motDEC >= 50 and initstep3_DEC == False and init_DEC_clockwise == True:
                initstep2_DEC = True
                step16DEC.value(False)
                #print("initstep2_DEC clockwise", initstep2_DEC)
                speed_motDEC = 50
                motorDEC.set_steps_per_second(speed_motDEC)
            elif slowdownminus <= declination < 0 and speed_motDEC >= 10 and initstep4_DEC == False and init_DEC_clockwise == True:
                initstep3_DEC = True
                step16DEC.value(False)
                #print("initstep3_DEC clockwise", initstep3_DEC)
                speed_motDEC = speed_motDEC -5
                motorDEC.set_steps_per_second(speed_motDEC)
            elif slowdownminus < declination < 0 and speed_motDEC < 10 and init_DEC_finished == False and init_DEC_clockwise == True:
                initstep4_DEC = True
                step16DEC.value(True)
                #print("initstep4_DEC clockwise", initstep4_DEC)
                speed_motDEC = 10
                motorDEC.set_steps_per_second(speed_motDEC)
        elif declination > zeropoint and init_DEC_clockwise == True:
            init_DEC_finished = True
            g_init_finished = True
            step16DEC.value(False)
            speed_motDEC = 0
            motorDEC.set_steps_per_second(speed_motDEC)
            print("init_DEC_finished clockwise", init_DEC_finished)
            print("g_ra_init", g_ra_init)
            print("g_dec_init", g_dec_init)
            break"""
            
    # ------------------ DEC Goto Init Position Anti Clock Wise ------------------ #
        declination = g_dec_init
        if declination > zeropoint and init_DEC_clockwise == False and init_RA_finished == True and init_DEC_finished == False:
            #print("g_dec_init", g_dec_init)
            init_DEC_anticlockwise = True
            init_DEC_clockwise = False
            if declination > slowdownplus and 0 >= speed_motDEC > -20 and initstep2_DEC == False and init_DEC_anticlockwise == True:
                initstep1_DEC = True
                step16DEC.value(False)
                #print("initstep1_DEC anticlockwise", initstep1_DEC)
                speed_motDEC = speed_motDEC -5
                motorDEC.set_steps_per_second(speed_motDEC)
            elif declination > slowdownplus and speed_motDEC <= -20 and initstep3_DEC == False and init_DEC_anticlockwise == True:
                initstep2_DEC = True
                step16DEC.value(False)
                #print("initstep2_DEC anticlockwise", initstep2_DEC)
                speed_motDEC = -20
                motorDEC.set_steps_per_second(speed_motDEC)
            elif slowdownplus >= declination > 0 and speed_motDEC <= -10 and initstep4_DEC == False and init_DEC_anticlockwise == True:
                initstep3_DEC = True
                step16DEC.value(False)
                #print("initstep3_DEC anticlockwise", initstep3_DEC)
                speed_motDEC = speed_motDEC +5
                motorDEC.set_steps_per_second(speed_motDEC)
            elif slowdownplus > declination > 0 and speed_motDEC > -10 and init_DEC_finished == False and init_DEC_anticlockwise == True:
                initstep4_DEC = True
                step16DEC.value(True)
                #print("initstep4_DEC anticlockwise", initstep4_DEC)
                speed_motDEC = -10
                motorDEC.set_steps_per_second(speed_motDEC)
        elif declination < zeropoint and init_DEC_anticlockwise == True:
            init_DEC_finished = True
            g_init_finished = True
            step16DEC.value(False)
            speed_motDEC = 0
            motorDEC.set_steps_per_second(speed_motDEC)
            print("init_DEC_finished anticlockwise", init_DEC_finished)
            print("g_ra_init", g_ra_init)
            print("g_dec_init", g_dec_init)
            break
        await asyncio.sleep(0.1)

# -------------------------------------------------------------------------------- #
    # ------------------ RA Goto Stellarium Position Clock Wise ------------------ #
    """while True:
        rightascension = g_ra_init
        if rightascension > zeropoint and init_RA_anticlockwise == False and init_RA_finished == False:
            #print("rightascension", rightascension)
            init_RA_clockwise = True
            init_RA_anticlockwise = False
            if rightascension > slowdownplus and 0 <= speed_motRA < 20 and initstep2_RA == False and init_RA_clockwise == True:
                initstep1_RA = True
                step16RA.value(False)
                #print("initstep1_RA clockwise", initstep1_RA)
                speed_motRA = speed_motRA +5
                motorRA.set_steps_per_second(speed_motRA)
            elif rightascension > slowdownplus and speed_motRA >= 20 and initstep3_RA == False and init_RA_clockwise == True:
                initstep2_RA = True
                step16RA.value(False)
                #print("initstep2_RA clockwise", initstep2_RA)
                speed_motRA = 20
                motorRA.set_steps_per_second(speed_motRA)
            elif slowdownplus >= rightascension > zeropoint and speed_motRA >= 10 and initstep4_RA == False and init_RA_clockwise == True:
                initstep3_RA = True
                step16RA.value(False)
                #print("initstep3_RA clockwise", initstep3_RA)
                speed_motRA = speed_motRA -5
                motorRA.set_steps_per_second(speed_motRA)
            elif slowdownplus > rightascension > zeropoint and speed_motRA < 10 and init_RA_finished == False and init_RA_clockwise == True:
                initstep4_RA = True
                step16RA.value(True)
                #print("initstep4_RA clockwise", initstep4_RA)
                speed_motRA = 10
                motorRA.set_steps_per_second(speed_motRA)
        elif rightascension < zeropoint and init_RA_clockwise == True:
            init_RA_finished = True
            step16RA.value(False)
            speed_motRA = 0
            motorRA.set_steps_per_second(speed_motRA)
            #print("init_RA_finished clockwise", init_RA_finished)

        # ------------------ RA Goto Stellarium Position Anti Clock Wise ------------------ #
        if rightascension < zeropoint and init_RA_clockwise == False and init_RA_finished == False:
            init_RA_anticlockwise = True
            init_RA_clockwise = False
            if rightascension < slowdownminus and 0 >= speed_motRA > -50 and initstep2_RA == False and init_RA_anticlockwise == True:
                initstep1_RA = True
                step16RA.value(False)
                #print("initstep1_RA anticlockwise", initstep1_RA)
                speed_motRA = speed_motRA -5
                motorRA.set_steps_per_second(speed_motRA)
            elif rightascension < slowdownminus and speed_motRA <= -50 and initstep3_RA == False and init_RA_anticlockwise == True:
                initstep2_RA = True
                step16RA.value(False)
                #print("initstep2_RA anticlockwise", initstep2_RA)
                speed_motRA = -50
                motorRA.set_steps_per_second(speed_motRA)
            elif slowdownminus <= rightascension < 0 and speed_motRA <= -10 and initstep4_RA == False and init_RA_anticlockwise == True:
                initstep3_RA = True
                step16RA.value(False)
                #print("initstep3_RA anticlockwise", initstep3_RA)
                speed_motRA = speed_motRA +5
                motorRA.set_steps_per_second(speed_motRA)
            elif slowdownminus < rightascension < 0 and speed_motRA > -10 and init_RA_finished == False and init_RA_anticlockwise == True:
                initstep4_RA = True
                step16RA.value(True)
                #print("initstep4_RA anticlockwise", initstep4_RA)
                speed_motRA = -10
                motorRA.set_steps_per_second(speed_motRA)
        elif rightascension > zeropoint and init_RA_anticlockwise == True:
            init_RA_finished = True
            step16RA.value(False)
            speed_motRA = 0
            motorRA.set_steps_per_second(speed_motRA)
            #print("init_RA_finished anticlockwise", init_RA_finished)


    # ------------------ DEC Goto Stellarium Position Clock Wise ------------------ #
        declination = g_dec_init
        if declination < zeropoint and init_DEC_anticlockwise == False and init_RA_finished == True and init_DEC_finished == False:
            init_DEC_clockwise = True
            init_DEC_anticlockwise = False
            if declination < slowdownminus and 0 <= speed_motDEC < 50 and initstep2_DEC == False and init_DEC_clockwise == True:
                initstep1_DEC = True
                step16DEC.value(False)
                #print("initstep1_DEC clockwise", initstep1_DEC)
                speed_motDEC = speed_motDEC +5
                motorDEC.set_steps_per_second(speed_motDEC)
            elif declination < slowdownminus and speed_motDEC >= 50 and initstep3_DEC == False and init_DEC_clockwise == True:
                initstep2_DEC = True
                step16DEC.value(False)
                #print("initstep2_DEC clockwise", initstep2_DEC)
                speed_motDEC = 50
                motorDEC.set_steps_per_second(speed_motDEC)
            elif slowdownminus <= declination < 0 and speed_motDEC >= 10 and initstep4_DEC == False and init_DEC_clockwise == True:
                initstep3_DEC = True
                step16DEC.value(False)
                #print("initstep3_DEC clockwise", initstep3_DEC)
                speed_motDEC = speed_motDEC -5
                motorDEC.set_steps_per_second(speed_motDEC)
            elif slowdownminus < declination < 0 and speed_motDEC < 10 and init_DEC_finished == False and init_DEC_clockwise == True:
                initstep4_DEC = True
                step16DEC.value(True)
                #print("initstep4_DEC clockwise", initstep4_DEC)
                speed_motDEC = 10
                motorDEC.set_steps_per_second(speed_motDEC)
        elif declination > zeropoint and init_DEC_clockwise == True:
            init_DEC_finished = True
            g_init_finished = True
            step16DEC.value(False)
            speed_motDEC = 0
            motorDEC.set_steps_per_second(speed_motDEC)
            print("init_DEC_finished clockwise", init_DEC_finished)
            print("g_ra_init", g_ra_init)
            print("g_dec_init", g_dec_init)
            
            
    # ------------------ DEC Goto Stellarium Position Anti Clock Wise ------------------ #
        declination = g_dec_init
        if declination > zeropoint and init_DEC_clockwise == False and init_RA_finished == True and init_DEC_finished == False:
            #print("g_dec_init", g_dec_init)
            init_DEC_anticlockwise = True
            init_DEC_clockwise = False
            if declination > slowdownplus and 0 >= speed_motDEC > -20 and initstep2_DEC == False and init_DEC_anticlockwise == True:
                initstep1_DEC = True
                step16DEC.value(False)
                #print("initstep1_DEC anticlockwise", initstep1_DEC)
                speed_motDEC = speed_motDEC -5
                motorDEC.set_steps_per_second(speed_motDEC)
            elif declination > slowdownplus and speed_motDEC <= -20 and initstep3_DEC == False and init_DEC_anticlockwise == True:
                initstep2_DEC = True
                step16DEC.value(False)
                #print("initstep2_DEC anticlockwise", initstep2_DEC)
                speed_motDEC = -20
                motorDEC.set_steps_per_second(speed_motDEC)
            elif slowdownplus >= declination > 0 and speed_motDEC <= -10 and initstep4_DEC == False and init_DEC_anticlockwise == True:
                initstep3_DEC = True
                step16DEC.value(False)
                #print("initstep3_DEC anticlockwise", initstep3_DEC)
                speed_motDEC = speed_motDEC +5
                motorDEC.set_steps_per_second(speed_motDEC)
            elif slowdownplus > declination > 0 and speed_motDEC > -10 and init_DEC_finished == False and init_DEC_anticlockwise == True:
                initstep4_DEC = True
                step16DEC.value(True)
                #print("initstep4_DEC anticlockwise", initstep4_DEC)
                speed_motDEC = -10
                motorDEC.set_steps_per_second(speed_motDEC)
        elif declination < zeropoint and init_DEC_anticlockwise == True:
            init_DEC_finished = True
            g_init_finished = True
            step16DEC.value(False)
            speed_motDEC = 0
            motorDEC.set_steps_per_second(speed_motDEC)
            print("init_DEC_finished anticlockwise", init_DEC_finished)
            print("g_ra_init", g_ra_init)
            print("g_dec_init", g_dec_init)
        await asyncio.sleep(0.1)"""

# ---------------- Async: Set Altitude Correction ------------------
async def alt_correction():
    global g_scope_RA, g_scope_DEC, g_scope_init
    altitude = 0
    
    while True:    
        altitude = float(g_dec_init)/100/65536*360 + g_my_latitude
        print("altitude", altitude)
        if altitude > -0.1 and g_init_finished == True:
            g_scope_init = True
            break

        await asyncio.sleep(1)


# ---------------- Async: Serial Data from/to Stellarium ------------------
async def readwrite_stellarium():

    stellarium_uart = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1))
    stellarium_uart.init(bits=8, parity=None, stop=1)
    print(stellarium_uart)

    #LX200 format does not work for micropython due to special character used
    #NexStar format
    #e = '00000000,C0000000#' #Equatorial South Pole coordinates 0, 270 degrees in Nexstar values, capital letters needed!

    NextStar_cmd = None
    NextStar_cmdchr0 = None

    while True:
        e = g_precise_RA_DEC
        if stellarium_uart.any(): 
            NextStar_cmd = stellarium_uart.read()
            NextStar_cmdchr0 = chr(NextStar_cmd[0])
            print(NextStar_cmdchr0)
            try:
                #if NextStar_cmd == b'e':
                if NextStar_cmdchr0 == 'e':
                    print(e)
                    stellarium_uart.write(e)
                elif NextStar_cmdchr0 == 'r':
                    print(NextStar_cmd)
                    msg = str(NextStar_cmd, 'utf-8')
                    print(msg)
                    ra_int = int((str(msg[1:6])), 16) # take first 6 hex numbers and convert to int
                    print(ra_int)
                else:
                    pass
            except:
                pass
        await asyncio.sleep(0.25)


# ---------------- Main Program Loop ------------------
async def main():
    asyncio.create_task(read_gps())
    asyncio.create_task(read_radec())
    asyncio.create_task(goto_init())
    asyncio.create_task(alt_correction())
    asyncio.create_task(readwrite_stellarium())
    #asyncio.create_task(write_ra_stepper())
    
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


