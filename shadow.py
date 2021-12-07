
import argparse
from awscrt import auth, io, mqtt, http
from awsiot import iotshadow
from awsiot import mqtt_connection_builder
from concurrent.futures import Future
import sys
import threading
import traceback
from uuid import uuid4
import time
import authenticate_user
import make_drink

# - Overview -
# This sample uses the AWS IoT Device Shadow Service to keep a property in
# sync between device and server. Imagine a light whose color may be changed
# through an app, or set by a local user.
#
# - Instructions -
# Once connected, type a value in the terminal and press Enter to update
# the property's "reported" value. The sample also responds when the "desired"
# value changes on the server. To observe this, edit the Shadow document in
# the AWS Console and set a new "desired" value.
#
# - Detail -
# On startup, the sample requests the shadow document to learn the property's
# initial state. The sample also subscribes to "delta" events from the server,
# which are sent when a property's "desired" value differs from its "reported"
# value. When the sample learns of a new desired value, that value is changed
# on the device and an update is sent to the server with the new "reported"
# value.

parser = argparse.ArgumentParser(description="Device Shadow sample keeps a property in sync across client and server")
parser.add_argument('--endpoint', required=True, help="Your AWS IoT custom endpoint, not including a port. " +
                                                      "Ex: \"w6zbse3vjd5b4p-ats.iot.us-west-2.amazonaws.com\"")
parser.add_argument('--cert',  help="File path to your client certificate, in PEM format")
parser.add_argument('--key', help="File path to your private key file, in PEM format")
parser.add_argument('--root-ca', help="File path to root certificate authority, in PEM format. " +
                                      "Necessary if MQTT server uses a certificate that's not already in " +
                                      "your trust store")
parser.add_argument('--client-id', default="test-" + str(uuid4()), help="Client ID for MQTT connection.")
parser.add_argument('--thing-name', required=True, help="The name assigned to your IoT Thing")
parser.add_argument('--shadow-property', default="color", help="Name of property in shadow to keep in sync")
parser.add_argument('--use-websocket', default=False, action='store_true',
    help="To use a websocket instead of raw mqtt. If you " +
    "specify this option you must specify a region for signing.")
parser.add_argument('--signing-region', default='us-east-1', help="If you specify --use-web-socket, this " +
    "is the region that will be used for computing the Sigv4 signature")
parser.add_argument('--proxy-host', help="Hostname of proxy to connect to.")
parser.add_argument('--proxy-port', type=int, default=8080, help="Port of proxy to connect to.")
parser.add_argument('--verbosity', choices=[x.name for x in io.LogLevel], default=io.LogLevel.NoLogs.name,
    help='Logging level')

# Using globals to simplify sample code
is_sample_done = threading.Event()

mqtt_connection = None
shadow_client = None
thing_name = ""

STATE = 0
UNAUTHED = 'UNAUTHORIZED'
WAITING  = 'WAITING'
MAKING   = 'MAKING'
FINISHED = 'FINISHED'


SHADOW_VALUE_DEFAULT = "off"

class LockedData:
    def __init__(self):
        self.lock = threading.Lock()

        self.drink = ''
        self.status = "UNAUTHED"
        self.authorized = False
        self.STATE = 0

        self.disconnect_called = False
        self.request_tokens = set()

class State:
    def __init__(self,d,s,a):
        self.drink = d
        self.status = s
        self.authorized = a


locked_data = LockedData()

# Function for gracefully quitting this sample
def exit(msg_or_exception):
    if isinstance(msg_or_exception, Exception):
        print("Exiting sample due to exception.")
        traceback.print_exception(msg_or_exception.__class__, msg_or_exception, sys.exc_info()[2])
    else:
        print("Exiting sample:", msg_or_exception)

    with locked_data.lock:
        if not locked_data.disconnect_called:
            print("Disconnecting...")
            locked_data.disconnect_called = True
            future = mqtt_connection.disconnect()
            future.add_done_callback(on_disconnected)

def on_disconnected(disconnect_future):
    # type: (Future) -> None
    print("Disconnected.")

    # Signal that sample is finished
    is_sample_done.set()



#  This is the callback function for whenever a get accepted is published from AWS
#  get/accepted contains the data response of a get request.

# NOT NECESSARY

# def on_get_shadow_accepted(response):
#     # type: (iotshadow.GetShadowResponse) -> None
#     try:
#         with locked_data.lock:
#             # check that this is a response to a request from this session
#             try:
#                 locked_data.request_tokens.remove(response.client_token)
#             except KeyError:
#                 print("Ignoring get_shadow_accepted message due to unexpected token.")
#                 return

#             print("Finished getting initial shadow state.")
#             if locked_data.shadow_value is not None:
#                 print("  Ignoring initial query because a delta event has already been received.")
#                 return

#         # TODO UPDATE THIS TO NEW PROPS
#         if response.state:
#             if response.state.delta:
#                 value = response.state.delta.get(shadow_property)
#                 if value:
#                     print("  Shadow contains delta value '{}'.".format(value))
#                     change_shadow_value(value)
#                     return

#             if response.state.reported:
#                 value = response.state.reported.get(shadow_property)
#                 if value:
#                     print("  Shadow contains reported value '{}'.".format(value))
#                     set_local_value_due_to_initial_query(response.state.reported[shadow_property])
#                     return

#         print("  Shadow document lacks '{}' property. Setting defaults...".format(shadow_property))
#         change_shadow_value(SHADOW_VALUE_DEFAULT)
#         return

#     except Exception as e:
#         exit(e)

# Get response when there is an error.
# Terminates program
def on_get_shadow_rejected(error):
    # type: (iotshadow.ErrorResponse) -> None
    try:
        # check that this is a response to a request from this session
        with locked_data.lock:
            try:
                locked_data.request_tokens.remove(error.client_token)
            except KeyError:
                print("Ignoring get_shadow_rejected message due to unexpected token.")
                return

        if error.code == 404:
            print("Thing has no shadow document. Creating with defaults...")
            default_state = State('',UNAUTHED,False)
            change_state_values(default_state)
        else:
            exit("Get request was rejected. code:{} message:'{}'".format(
                error.code, error.message))

    except Exception as e:
        exit(e)




# Receives info from website
# This is the callback function when update is pushed and there is a change between requested and current state
def on_shadow_delta_updated(delta):
    # type: (iotshadow.ShadowDeltaUpdatedEvent) -> None
    if  not locked_data.authorized:
        print("Not Authorized to user the bar.")
        return

    if locked_data.STATE != WAITING:
        print("Bar received update while it was making drink. Update Ignored.")
        return


    try:
        print("Received shadow delta event.")

        if delta.state.drink != '' and locked_data.drink == '': 
            new_state = State(delta.state.drink,MAKING,locked_data.authorized)
            change_state_values(new_state)
            

    except Exception as e:
        exit(e)





# I dont really know what future.result() is
def on_publish_update_shadow(future):
    #type: (Future) -> None
    try:
        future.result()
        print("Update request published.")
    except Exception as e:
        print("Failed to publish update request.")
        exit(e)

# # Response when shadow is updated (not sure if it triggers with delta as well)
# def on_update_shadow_accepted(response):
#     # type: (iotshadow.UpdateShadowResponse) -> None
#     try:
#         # check that this is a response to a request from this session
#         with locked_data.lock:
#             try:
#                 locked_data.request_tokens.remove(response.client_token)
#             except KeyError:
#                 print("Ignoring update_shadow_accepted message due to unexpected token.")
#                 return
#         print("Finished updating reported shadow value." ) # type: ignore

#     except Exception as e:
#         exit(e)

# Error --> terminate programs
def on_update_shadow_rejected(error):
    # type: (iotshadow.ErrorResponse) -> None
    try:
        # check that this is a response to a request from this session
        with locked_data.lock:
            try:
                locked_data.request_tokens.remove(error.client_token)
            except KeyError:
                print("Ignoring update_shadow_rejected message due to unexpected token.")
                return

        exit("Update request was rejected. code:{} message:'{}'".format(
            error.code, error.message))

    except Exception as e:
        exit(e)


#  UPDATE THIS TO NEW PROPS
def set_local_value_due_to_initial_query(reported_value):
    with locked_data.lock:
        locked_data.shadow_value = reported_value



# This functions updates the value of authorization on the device and then lets AWS know.
def change_authorization_value(auth):
    with locked_data.lock:
        if locked_data.authorized == auth:
            print("User is already authenticated")
            return

        print("Changed local shadow value to '{}'.".format(auth))
        locked_data.authorized = auth
        print("Updating reported shadow value to '{}'...".format(auth))

        # use a unique token so we can correlate this "request" message to
        # any "response" messages received on the /accepted and /rejected topics
        token = str(uuid4())

        request = iotshadow.UpdateShadowRequest(
            thing_name=thing_name,
            state=iotshadow.ShadowState(
                reported={ "drink": locked_data.drink, "auth": auth, "status": locked_data.status },
                desired={ "drink": locked_data.drink, "auth": auth, "status": locked_data.status },
            ),
            client_token=token,
        )
        future = shadow_client.publish_update_shadow(request, mqtt.QoS.AT_LEAST_ONCE)
        locked_data.request_tokens.add(token)
        future.add_done_callback(on_publish_update_shadow)

# This functions updates the status on the device and then lets AWS know.
def change_status_value(status):
    with locked_data.lock:
        if locked_data.status == status:
            print("Device is already on status: '{}.".format(status))
            return

        print("Changed local shadow status to '{}'.".format(status))
        locked_data.status = status
        print("Updating reported shadow status to '{}'...".format(status))

        # use a unique token so we can correlate this "request" message to
        # any "response" messages received on the /accepted and /rejected topics
        token = str(uuid4())

        request = iotshadow.UpdateShadowRequest(
            thing_name=thing_name,
            state=iotshadow.ShadowState(
                reported={ "drink": locked_data.drink, "auth": locked_data.authorized, "status": status },
                desired={ "drink": locked_data.drink, "auth": locked_data.authorized, "status": status },
            ),
            client_token=token,
        )
        future = shadow_client.publish_update_shadow(request, mqtt.QoS.AT_LEAST_ONCE)
        locked_data.request_tokens.add(token)
        future.add_done_callback(on_publish_update_shadow)

# This functions updates the status on the device and then lets AWS know.
def change_drink_value(drink):
    with locked_data.lock:
        if locked_data.drink == drink:
            print("Device is already on that drink: '{}.".format(drink))
            return

        print("Changed local shadow status to '{}'.".format(drink))
        locked_data.drink = drink
        print("Updating reported shadow status to '{}'...".format(drink))

        # use a unique token so we can correlate this "request" message to
        # any "response" messages received on the /accepted and /rejected topics
        token = str(uuid4())

        request = iotshadow.UpdateShadowRequest(
            thing_name=thing_name,
            state=iotshadow.ShadowState(
                reported={ "drink": drink, "auth": locked_data.authorized, "status": locked_data.status },
                desired={  "drink": drink, "auth": locked_data.authorized, "status": locked_data.status },
            ),
            client_token=token,
        )
        future = shadow_client.publish_update_shadow(request, mqtt.QoS.AT_LEAST_ONCE)
        locked_data.request_tokens.add(token)
        future.add_done_callback(on_publish_update_shadow)

def change_state_values(state: State):
    with locked_data.lock:
        if locked_data.drink == state.drink and locked_data.authorized == state.authorized and locked_data.status == state.status:
            print("Device is already on set.")
            return

        print("Changed local shadow status.")

        locked_data.drink = state.drink
        locked_data.authorized = state.authorized
        locked_data.status = state.status

        print("Updating reported shadow status on AWS ")

        # use a unique token so we can correlate this "request" message to
        # any "response" messages received on the /accepted and /rejected topics
        token = str(uuid4()) 

        request = iotshadow.UpdateShadowRequest(
            thing_name=thing_name,
            state=iotshadow.ShadowState(
                reported={ "drink": locked_data.drink, "auth": locked_data.authorized, "status": locked_data.status },
                desired={  "drink": locked_data.drink, "auth": locked_data.authorized, "status": locked_data.status },
            ),
            client_token=token,
        )
        future = shadow_client.publish_update_shadow(request, mqtt.QoS.AT_LEAST_ONCE)
        locked_data.request_tokens.add(token)
        future.add_done_callback(on_publish_update_shadow)






# Main thread


def user_input_thread_fn():

    locked_data.drink = ''
    locked_data.status = "UNAUTHED"
    locked_data.authorized = False
    
    try:
        # Callbacks baby
        while(1):
            if locked_data.STATE == UNAUTHED:
                authenticate_user()
            elif locked_data.STATE == WAITING:
                continue
            elif locked_data.STATE == MAKING:
                make_drink()
                change_status_value(FINISHED)
            elif locked_data.STATE == FINISHED:
                time.sleep(5)
                change_status_value(WAITING)
            else:
                default_state = State('',UNAUTHED,False)
                change_state_values(default_state)
    except Exception as e:
        print("Exception on input thread.")
        exit(e)
        








# Main: sets everything up and then calls main thread



if __name__ == '__main__':
    # Process input args
    args = parser.parse_args()
    thing_name = args.thing_name
    shadow_property = args.shadow_property
    io.init_logging(getattr(io.LogLevel, args.verbosity), 'stderr')

    # Spin up resources
    event_loop_group = io.EventLoopGroup(1)
    host_resolver = io.DefaultHostResolver(event_loop_group)
    client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)

    proxy_options = None
    if (args.proxy_host):
        proxy_options = http.HttpProxyOptions(host_name=args.proxy_host, port=args.proxy_port)

    if args.use_websocket == True:
        credentials_provider = auth.AwsCredentialsProvider.new_default_chain(client_bootstrap)
        mqtt_connection = mqtt_connection_builder.websockets_with_default_aws_signing(
            endpoint=args.endpoint,
            client_bootstrap=client_bootstrap,
            region=args.signing_region,
            credentials_provider=credentials_provider,
            http_proxy_options=proxy_options,
            ca_filepath=args.root_ca,
            client_id=args.client_id,
            clean_session=True,
            keep_alive_secs=30)

    else:
        mqtt_connection = mqtt_connection_builder.mtls_from_path(
            endpoint=args.endpoint,
            cert_filepath=args.cert,
            pri_key_filepath=args.key,
            client_bootstrap=client_bootstrap,
            ca_filepath=args.root_ca,
            client_id=args.client_id,
            clean_session=True,
            keep_alive_secs=30,
            http_proxy_options=proxy_options)

    print("Connecting to {} with client ID '{}'...".format(
        args.endpoint, args.client_id))

    connected_future = mqtt_connection.connect()

    shadow_client = iotshadow.IotShadowClient(mqtt_connection)

    # Wait for connection to be fully established.
    # Note that it's not necessary to wait, commands issued to the
    # mqtt_connection before its fully connected will simply be queued.
    # But this sample waits here so it's obvious when a connection
    # fails or succeeds.
    connected_future.result()
    print("Connected!")

    try:
        # Subscribe to necessary topics.
        # Note that is **is** important to wait for "accepted/rejected" subscriptions
        # to succeed before publishing the corresponding "request".
        print("Subscribing to Update responses...")
        # update_accepted_subscribed_future, _ = shadow_client.subscribe_to_update_shadow_accepted(
        #     request=iotshadow.UpdateShadowSubscriptionRequest(thing_name=args.thing_name),
        #     qos=mqtt.QoS.AT_LEAST_ONCE,
        #     callback=on_update_shadow_accepted)

        # update_accepted_subscribed_future.result()

        update_rejected_subscribed_future, _ = shadow_client.subscribe_to_update_shadow_rejected(
            request=iotshadow.UpdateShadowSubscriptionRequest(thing_name=args.thing_name),
            qos=mqtt.QoS.AT_LEAST_ONCE,
            callback=on_update_shadow_rejected)

        # Wait for subscriptions to succeed
        
        update_rejected_subscribed_future.result()

        print("Subscribing to Get responses...")
        # get_accepted_subscribed_future, _ = shadow_client.subscribe_to_get_shadow_accepted(
        #     request=iotshadow.GetShadowSubscriptionRequest(thing_name=args.thing_name),
        #     qos=mqtt.QoS.AT_LEAST_ONCE,
        #     callback=on_get_shadow_accepted)

        # get_accepted_subscribed_future.result()


        get_rejected_subscribed_future, _ = shadow_client.subscribe_to_get_shadow_rejected(
            request=iotshadow.GetShadowSubscriptionRequest(thing_name=args.thing_name),
            qos=mqtt.QoS.AT_LEAST_ONCE,
            callback=on_get_shadow_rejected)

        # Wait for subscriptions to succeed
        get_rejected_subscribed_future.result()

        print("Subscribing to Delta events...")
        delta_subscribed_future, _ = shadow_client.subscribe_to_shadow_delta_updated_events(
            request=iotshadow.ShadowDeltaUpdatedSubscriptionRequest(thing_name=args.thing_name),
            qos=mqtt.QoS.AT_LEAST_ONCE,
            callback=on_shadow_delta_updated)

        # Wait for subscription to succeed
        delta_subscribed_future.result()

        # The rest of the sample runs asynchronously.



        # TODO Instead of getting state, send current state on boot up
        # # Issue request for shadow's current state.
        # # The response will be received by the on_get_accepted() callback
        # print("Requesting current shadow state...")

        # with locked_data.lock:
        #     # use a unique token so we can correlate this "request" message to
        #     # any "response" messages received on the /accepted and /rejected topics
        #     token = str(uuid4())

        #     publish_get_future = shadow_client.publish_get_shadow(
        #         request=iotshadow.GetShadowRequest(thing_name=args.thing_name, client_token=token),
        #         qos=mqtt.QoS.AT_LEAST_ONCE)

        #     locked_data.request_tokens.add(token)

        # # Ensure that publish succeeds
        # publish_get_future.result()

        # Launch thread to handle user input.
        # A "daemon" thread won't prevent the program from shutting down.
        print("Launching thread to read user input...")
        user_input_thread = threading.Thread(target=user_input_thread_fn, name='user_input_thread')
        user_input_thread.daemon = True
        user_input_thread.start()

    except Exception as e:
        exit(e)

    # Wait for the sample to finish (user types 'quit', or an error occurs)
    is_sample_done.wait()

# Website can only send desired drink updates
# Device sends reported Status, Drink, Auth updates

# TODO make drink maker function
    #  once drink is made and it goes from finishing to waiting, set drink to None
# TODO implement user authentication