import time
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient

def helloworld(self, params, packet):
    print ('Received message from IoT Core')
    print ('Topic: ' + packet.topic)
    print ("Payload: ", (packet.payload))

myMQTTClient = AWSIoTMQTTClient("CustomerId") #random key, if another connection using the same key is opened the previous one is auto closed by AWS IOT
myMQTTClient.configureEndpoint("a1fs6jiodvpd9q-ats.iot.us-east-2.amazonaws.com", 8883)

myMQTTClient.configureCredentials("", "", "")

myMQTTClient.configureOfflinePublishQueueing(-1) # Infintie offlien Publish queueing
myMQTTClient.configureDrainingFrequency(2) # Draining: 2 Hz
myMQTTClient.configureConnectDisconnectTimeout(10) # 10 sec
myMQTTClient.configureMQTTOperationTimeout(5) # 5 sec
print ('Initiating IoT Core Topic ...')
myMQTTClient.connect()
# myMQTTClient.subscribe("hello/helloworld", 1, helloworld)

# while True:
#         time.sleep(5)

print("Publishing Message from RPI")
myMQTTClient.publish(
    topic= "home/helloworld",
    QoS=1,
    payload="{'Message': 'Message By RPI'}"
)