#code to run the ultrasonic sensor

import RPi.GPIO as GPIO
import time
#import MySQLdb
import datetime
from awscommunicate import AWS_CONNECT, publish

import face_recognition
import picamera
import numpy as np


#connect the database object

client = AWS_CONNECT()
#db = MySQLdb.connect("localhost", "team", "kristi", "sensoryData")

#cursor = db.cursor()

echo = 20
trigger = 21
#digital = 16

GPIO.setmode(GPIO.BCM)

counter = 0

#GPIO.setup(digital, GPIO.OUT)
#time.sleep(0.2)
#GPIO.output(digital, True)

userFound = False

while (counter < 20 and userFound != True):
    print("measuring distance")
    GPIO.setup(trigger, GPIO.OUT)
    GPIO.setup(echo, GPIO.IN)
    GPIO.output(trigger, False)
    print("waiting on sensor")
    time.sleep(0.2)
    GPIO.output(trigger, True)
    time.sleep(0.00001)
    GPIO.output(trigger, False)
    
    while GPIO.input(echo)==0:
        pulse_start = time.time()
        
    while GPIO.input(echo)==1:
        pulse_end = time.time()
    
    dis = round((pulse_end - pulse_start)*17150, 2)
    
    print("distance: ", dis, "cm")
    
    time.sleep(2)
    
    title = "distance"
    
    
    try:
        publish(client, "home/helloworld", "DISTANCE", str(dis))
        print("AWS MESSAGE SENT")
    
    except:
        print("AWS ERROR")
    
    count = 0
    
    # Load a sample picture and learn how to recognize it.
    print("Loading known face image(s)")
    preston_image = face_recognition.load_image_file("preston.jpg")
    preston_face_encoding = face_recognition.face_encodings(preston_image)[0]
    print("preston done")
    joseph_image = face_recognition.load_image_file("joseph.jpg")
    joseph_face_encoding = face_recognition.face_encodings(joseph_image)[0]
    print("joseph done")
    
    while(count < 20 and dis < 200 and userFound != True):
        print("in our face loop")
        # Get a reference to the Raspberry Pi camera.
        # If this fails, make sure you have a camera connected to the RPi and that you
        # enabled your camera in raspi-config and rebooted first.
        camera = picamera.PiCamera()
        camera.resolution = (320, 240)
        output = np.empty((240, 320, 3), dtype=np.uint8)

        # Initialize some variables
        face_locations = []
        face_encodings = []
        
        face_not_found = True
        while face_not_found:
            print("Capturing image.")
            # Grab a single frame of video from the RPi camera as a numpy array
            camera.capture(output, format="rgb")

            # Find all the faces and face encodings in the current frame of video
            face_locations = face_recognition.face_locations(output)
            print("Found {} faces in image.".format(len(face_locations)))
            face_encodings = face_recognition.face_encodings(output, face_locations)

            # Loop over each face found in the frame to see if it's someone we know.
            for face_encoding in face_encodings:
                # See if the face is a match for the known face(s)
                match = face_recognition.compare_faces([preston_face_encoding,joseph_face_encoding], face_encoding)
                name = "<Unknown Person>"

                if match[0]:
                    name = "Preston"
                    
                    try:
                        publish(client, "home/helloworld", "Approved User Found: ", str(name))
                        print("AWS MESSAGE SENT")
                    except:
                        print("AWS ERROR")
                    
                    face_not_found = False
                    userFound = True
                    
                    break
                elif match[1]:
                    name = "Joseph"
                    
                    try:
                        publish(client, "home/helloworld", "Approved User Found: ", str(name))
                        print("AWS MESSAGE SENT")
                    except:
                        print("AWS ERROR") 
                    
                    face_not_found = False
                    userFound = True
                    
                    break
                else:
                    try:
                        publish(client, "home/helloworld", "User Not Approved: ", str(name))
                        print("AWS MESSAGE SENT")
            
                    except:
                        print("AWS ERROR")
                    
                    face_not_found = False
        
        count+=1                
    counter+=1           
    
    

    
