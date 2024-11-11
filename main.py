import asyncio
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
g_ra_init = 0.0
g_dec_init = 0.0
g_rightascension = 0.0
g_declination = 0.0
#g_pot_alt = 0.0
#g_pot_az = 0.0
g_scope_RA = None
g_scope_DEC = None
g_scope_ALT = None
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
    mpu = MPU6050(i2c)

    global g_rightascension, g_declination
    xGyro = 0
    yGyro = 0
    xRad = 0
    yRad = 0
    xDeg = 0
    yDeg = 0
    xDeg_comp = 0
    yDeg_comp = 0
    errorX = 0
    errorY = 0
    tLoop = 0

    while True:
        tStart=time.ticks_ms()

        xGyro=mpu.gyro.x

        xAccel = mpu.accel.x
        if xAccel > 1:
            xAccel = 1
        elif xAccel < -1:
            xAccel = -1
        xRad = math.asin(xAccel)
        xDeg = xRad/(2*math.pi)*360      
        xDeg_comp = xDeg*.50 + .50*(xDeg_comp+xGyro*tLoop)+errorX*.01
        
        errorX = errorX + (xDeg-xDeg_comp)*tLoop

        yGyro=mpu.gyro.y

        yAccel = mpu.accel.y
        if yAccel > 1:
            yAccel = 1
        elif yAccel < -1:
            yAccel = -1
        yRad = math.asin(yAccel)
        yDeg = yRad/(2*math.pi)*360      
        yDeg_comp = yDeg*.50 + .50*(yDeg_comp+yGyro*tLoop)+errorY*.01
        
        errorY = errorY + (yDeg-yDeg_comp)*tLoop        

        g_ra_init = xDeg_comp
        g_dec_init = yDeg_comp
        
        tStop=time.ticks_ms()
        tLoop=(tStop-tStart)*.001
        await asyncio.sleep(0.0001)        


# ---------------- Async: GOTO RA Init possition ------------------
async def goto_init():

    motorRA = Stepper(0, 10, 11)
    step16RA = Pin(12, Pin.OUT, value=False)               # GPIO12 Digital Output

    speed_motRA = 0
    Degslowdownplus = 10
    Degslowdownminus = -10
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
    Degslowdownplus = 10
    Degslowdownminus = -10
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
        if rightascension > 0 and init_RA_anticlockwise == False and init_RA_finished == False:
            init_RA_clockwise = True
            init_RA_anticlockwise = False
            if rightascension > Degslowdownplus and 0 <= speed_motRA < 50 and initstep2_RA == False and init_RA_clockwise == True:
                initstep1_RA = True
                step16RA.value(False)
                #print("initstep1_RA clockwise", initstep1_RA)
                speed_motRA = speed_motRA +5
                motorRA.set_steps_per_second(speed_motRA)
            elif rightascension > Degslowdownplus and speed_motRA >= 50 and initstep3_RA == False and init_RA_clockwise == True:
                initstep2_RA = True
                step16RA.value(False)
                #print("initstep2_RA clockwise", initstep2_RA)
                speed_motRA = 50
                motorRA.set_steps_per_second(speed_motRA)
            elif Degslowdownplus >= rightascension > 0 and speed_motRA >= 10 and initstep4_RA == False and init_RA_clockwise == True:
                initstep3_RA = True
                step16RA.value(False)
                #print("initstep3_RA clockwise", initstep3_RA)
                speed_motRA = speed_motRA -5
                motorRA.set_steps_per_second(speed_motRA)
            elif Degslowdownplus > rightascension > 0 and speed_motRA < 10 and init_RA_finished == False and init_RA_clockwise == True:
                initstep4_RA = True
                step16RA.value(True)
                #print("initstep4_RA clockwise", initstep4_RA)
                speed_motRA = 10
                motorRA.set_steps_per_second(speed_motRA)
        elif rightascension < 0 and init_RA_clockwise == True:
            init_RA_finished = True
            step16RA.value(False)
            speed_motRA = 0
            motorRA.set_steps_per_second(speed_motRA)
            #print("init_RA_finished clockwise", init_RA_finished)

        # ------------------ RA Goto Init Position Anti Clock Wise ------------------ #
        if rightascension < 0 and init_RA_clockwise == False and init_RA_finished == False:
            init_RA_anticlockwise = True
            init_RA_clockwise = False
            if rightascension < Degslowdownminus and 0 >= speed_motRA > -50 and initstep2_RA == False and init_RA_anticlockwise == True:
                initstep1_RA = True
                step16RA.value(False)
                #print("initstep1_RA anticlockwise", initstep1_RA)
                speed_motRA = speed_motRA -5
                motorRA.set_steps_per_second(speed_motRA)
            elif rightascension < Degslowdownminus and speed_motRA <= -50 and initstep3_RA == False and init_RA_anticlockwise == True:
                initstep2_RA = True
                step16RA.value(False)
                #print("initstep2_RA anticlockwise", initstep2_RA)
                speed_motRA = -50
                motorRA.set_steps_per_second(speed_motRA)
            elif Degslowdownminus <= rightascension < 0 and speed_motRA <= -10 and initstep4_RA == False and init_RA_anticlockwise == True:
                initstep3_RA = True
                step16RA.value(False)
                #print("initstep3_RA anticlockwise", initstep3_RA)
                speed_motRA = speed_motRA +5
                motorRA.set_steps_per_second(speed_motRA)
            elif Degslowdownminus < rightascension < 0 and speed_motRA > -10 and init_RA_finished == False and init_RA_anticlockwise == True:
                initstep4_RA = True
                step16RA.value(True)
                #print("initstep4_RA anticlockwise", initstep4_RA)
                speed_motRA = -10
                motorRA.set_steps_per_second(speed_motRA)
        elif rightascension > 0 and init_RA_anticlockwise == True:
            init_RA_finished = True
            step16RA.value(False)
            speed_motRA = 0
            motorRA.set_steps_per_second(speed_motRA)
            #print("init_RA_finished anticlockwise", init_RA_finished)


    # ------------------ DEC Goto Init Position Clock Wise ------------------ #
        declination = g_dec_init
        if declination < 0 and init_DEC_anticlockwise == False and init_RA_finished == True and init_DEC_finished == False:
            init_DEC_clockwise = True
            init_DEC_anticlockwise = False
            if declination < Degslowdownminus and 0 <= speed_motDEC < 50 and initstep2_DEC == False and init_DEC_clockwise == True:
                initstep1_DEC = True
                step16DEC.value(False)
                #print("initstep1_DEC clockwise", initstep1_DEC)
                speed_motDEC = speed_motDEC +5
                motorDEC.set_steps_per_second(speed_motDEC)
            elif declination < Degslowdownminus and speed_motDEC >= 50 and initstep3_DEC == False and init_DEC_clockwise == True:
                initstep2_DEC = True
                step16DEC.value(False)
                #print("initstep2_DEC clockwise", initstep2_DEC)
                speed_motDEC = 50
                motorDEC.set_steps_per_second(speed_motDEC)
            elif Degslowdownminus <= declination < 0 and speed_motDEC >= 10 and initstep4_DEC == False and init_DEC_clockwise == True:
                initstep3_DEC = True
                step16DEC.value(False)
                #print("initstep3_DEC clockwise", initstep3_DEC)
                speed_motDEC = speed_motDEC -5
                motorDEC.set_steps_per_second(speed_motDEC)
            elif Degslowdownminus < declination < 0 and speed_motDEC < 10 and init_DEC_finished == False and init_DEC_clockwise == True:
                initstep4_DEC = True
                step16DEC.value(True)
                #print("initstep4_DEC clockwise", initstep4_DEC)
                speed_motDEC = 10
                motorDEC.set_steps_per_second(speed_motDEC)
        elif declination > 0 and init_DEC_clockwise == True:
            init_DEC_finished = True
            step16DEC.value(False)
            speed_motDEC = 0
            motorDEC.set_steps_per_second(speed_motDEC)
            print("init_DEC_finished clockwise", init_DEC_finished)
            print("rightascension", rightascension)
            print("declination", declination)
            break
            
    # ------------------ DEC Goto Init Position Anti Clock Wise ------------------ #
        if declination > 0 and init_DEC_clockwise == False and init_RA_finished == True and init_DEC_finished == False:
            init_DEC_anticlockwise = True
            init_DEC_clockwise = False
            if declination > Degslowdownplus and 0 >= speed_motDEC > -50 and initstep2_DEC == False and init_DEC_anticlockwise == True:
                initstep1_DEC = True
                step16DEC.value(False)
                #print("initstep1_DEC anticlockwise", initstep1_DEC)
                speed_motDEC = speed_motDEC -5
                motorDEC.set_steps_per_second(speed_motDEC)
            elif declination > Degslowdownplus and speed_motDEC <= -50 and initstep3_DEC == False and init_DEC_anticlockwise == True:
                initstep2_DEC = True
                step16DEC.value(False)
                #print("initstep2_DEC anticlockwise", initstep2_DEC)
                speed_motDEC = -50
                motorDEC.set_steps_per_second(speed_motDEC)
            elif Degslowdownplus >= declination > 0 and speed_motDEC <= -10 and initstep4_DEC == False and init_DEC_anticlockwise == True:
                initstep3_DEC = True
                step16DEC.value(False)
                #print("initstep3_DEC anticlockwise", initstep3_DEC)
                speed_motDEC = speed_motDEC +5
                motorDEC.set_steps_per_second(speed_motDEC)
            elif Degslowdownplus > declination > 0 and speed_motDEC > -10 and init_DEC_finished == False and init_DEC_anticlockwise == True:
                initstep4_DEC = True
                step16DEC.value(True)
                #print("initstep4_DEC anticlockwise", initstep4_DEC)
                speed_motDEC = -10
                motorDEC.set_steps_per_second(speed_motDEC)
        elif declination < 0 and init_DEC_anticlockwise == True:
            init_DEC_finished = True
            step16DEC.value(False)
            speed_motDEC = 0
            motorDEC.set_steps_per_second(speed_motDEC)
            print("init_DEC_finished anticlockwise", init_DEC_finished)
            print("rightascension", rightascension)
            print("declination", declination)
            break
        await asyncio.sleep(0.1)

# ---------------- Async: Set Altitude Correction ------------------
async def alt_correction():
    altitude = 0

    while True:    
        altitude = g_declination + g_my_latitude
        print("altitude correction", altitude)

            
        await asyncio.sleep(1)


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
    e = '34AB0500,12CE0500#'
    NextStar_cmd = None

    while True:
        if stellarium_uart.any(): 
            NextStar_cmd = stellarium_uart.read()
            print(NextStar_cmd)
            try:
                if NextStar_cmd == b'e':
                    print(e)
                    stellarium_uart.write(e)    
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


