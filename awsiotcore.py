import time
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient

myMQTTClient = AWSIoTMQTTClient("CustomerId") #random key, if another connection using the same key is opened the previous one is auto closed by AWS IOT
myMQTTClient.configureEndpoint("a1fs6jiodvpd9q-ats.iot.us-east-2.amazonaws.com", 8883)

myMQTTClient.configureCredentials("")