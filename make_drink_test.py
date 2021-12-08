import RPi.GPIO as GPIO
import time
#import MySQLdb
import datetime

GPIO.setmode(GPIO.BCM)


SPRITE = 3
ORANGE_JUICE = 4
LIQUID_3 = 17
LIQUID_4 = 27

ON = False
OFF = True

GPIO.setup(SPRITE,GPIO.OUT)
GPIO.setup(ORANGE_JUICE,GPIO.OUT)
GPIO.setup(LIQUID_3,GPIO.OUT)
GPIO.setup(LIQUID_4,GPIO.OUT)

c = 0
def make_drink_spritzer():
    
    print("Started")
    
    GPIO.output(SPRITE,ON)
    GPIO.output(ORANGE_JUICE,ON)

    time.sleep(4)

    GPIO.output(SPRITE,OFF)
    GPIO.output(ORANGE_JUICE,OFF)
    
    GPIO.output(LIQUID_3,ON)
    GPIO.output(LIQUID_4,ON)

    time.sleep(2)
    
    GPIO.output(LIQUID_3,OFF)
    GPIO.output(LIQUID_4,OFF)

    time.sleep(2)
    print("Finished Drink")


#while(c < 5):
 #   make_drink_spritzer()
  #  c+=1
    


#print("OFF")