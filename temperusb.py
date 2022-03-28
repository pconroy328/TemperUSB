"""
Temper - a class for managing a TEMPer USB temperature sensor

Bill Mania <bill@manialabs.us>

Source: http://www.manialabs.us/downloads/Temper.py


sudo pip3 install pyusb
still connecting to wrong MQTT broker

run sudo until I get the permissions figured out
"""

import usb.core
import sys
import json
import logging
import paho.mqtt.client as mqtt
import datetime
import time
import socket
import collections

class Temper():

    def __init__(self):

        self.devices = []
        self.calibrationConstant = 15
        self.units = 'C'

        self.device_list = usb.core.find(
                find_all=True,
                idVendor = 0x1130,
                idProduct = 0x660c
                )
        self.devices = [device for device in self.device_list]

        if self.devices is None:
            logging.error( 'Unable to find a temperature device' )
            return

        # Try our best to detach the device from any previous state
        try:
            for device in self.devices:
                if device.is_kernel_driver_active(0):
                    device.detach_kernel_driver(0)
                if device.is_kernel_driver_active(1):
                    device.detach_kernel_driver(1)
        except NotImplementedError as e:
            #Note: some system do not implement is_kernel_driver_active
            try:
                for device in self.devices:
                    device.detach_kernel_driver(0)
                    device.detach_kernel_driver(1)
            except Exception as e:
                # I give up, maybe we will get lucky anyway
                #print( "Exception: " + e.__class__.__name__ + ": " + str(e) )
                pass
        except Exception as e:
            #print( "Exception: " + e.__class__.__name__ + ": " + str(e) )
            pass

        # Configure the device
        for device in self.devices:
            try:
                # This attach would avoid the following kernel warning, but
                # generates 2 other attach lines.  A clean "claim" would be better.
                #   kernel warning: 'process xxx (python) did not claim interface 1 before use'
                #device.attach_kernel_driver(0)
                #device.attach_kernel_driver(1)
                #device.reset()
                device.set_configuration()
            except Exception as e:
                logging.error( "Error: Unable to setup the device")
                raise e
                #print( "Exception: " + e.__class__.__name__ + ": " + str(e))
                #return

        #
        # the following sequence appear to be necessary to
        # either calibrate or initialize the TEMPer, but I
        # have no idea why. therefore, I named them all "magic".
        #
        nullTrailer = ''
        for i in range(0, 24):
            nullTrailer = nullTrailer + chr(0)
        firstMagicSequence = chr(10) + chr(11) + chr(12) + chr(13)  + chr(0) + chr(0) + chr(2) + chr(0)
        firstMagicSequence = firstMagicSequence + nullTrailer
        secondMagicSequence = chr(0x54) + chr(0) + chr(0) + chr(0) + chr(0) + chr(0) + chr(0) + chr(0)
        secondMagicSequence = secondMagicSequence + nullTrailer
        thirdMagicSequence = chr(0) + chr(0) + chr(0) + chr(0) + chr(0) + chr(0) + chr(0) + chr(0)
        thirdMagicSequence = thirdMagicSequence + nullTrailer
        fourthMagicSequence = chr(10) + chr(11) + chr(12) + chr(13)  + chr(0) + chr(0) + chr(1) + chr(0)
        fourthMagicSequence = fourthMagicSequence + nullTrailer

        for device in self.devices:
            bytesSent = device.ctrl_transfer(
                0x21,
                9,
                0x200,
                0x1,
                firstMagicSequence,
                32
                )
            bytesSent = device.ctrl_transfer(
                0x21,
                9,
                0x200,
                0x1,
                secondMagicSequence,
                32
                )
            for i in range(0, 7):
                bytesSent = device.ctrl_transfer(
                    0x21,
                    9,
                    0x200,
                    0x1,
                    thirdMagicSequence,
                    32
                    )
            bytesSent = device.ctrl_transfer(
                0x21,
                9,
                0x200,
                0x1,
                fourthMagicSequence,
                32
                )

        return

    def setCalibration(self, calibrationConstant):
        self.calibrationConstant = calibrationConstant

        return

    def setUnits(self, units = 'C'):
        self.units = units

        return

    def getUnits(self):
        if self.units == 'C':
            return 'Celsius'
        elif self.units == 'F':
            return 'Fahrenheit'
        elif self.units == 'K':
            return 'Kelvin'
        else:
            return 'Unknown'

    def getTemperature(self, device):
        nullTrailer = ''
        for i in range(0, 24):
            nullTrailer = nullTrailer + chr(0)

        temperatureBuffer = device.ctrl_transfer(
            0xa1,
            1,
            0x300,
            0x1,
            256,
            0
            )

        if len(temperatureBuffer) > 1:
            if temperatureBuffer[0] == 0 and temperatureBuffer[1] == 255:
                logging.error( "Failed to retrieve temperature" )
                return 0.0
            #print( temperatureBuffer )
            temperature = int(temperatureBuffer[0] << 8) + int(temperatureBuffer[1] & 0xff) + self.calibrationConstant
            temperature = temperature * (125.0 / 32000.0)
            if self.units == 'F':
                temperature = 9.0 / 5.0 * temperature + 32.0
            elif self.units == 'K':
                temperature = temperature + 273.15
            else:
                pass

        else:
            logging.error( "Failed to retrieve temperature" )
            temperature = 0.0

        return temperature

    #-------------------------------------------------------------------------------
    def asJSON(self,deviceNumber=1,location='??',temperatureF=-99.99):
        time_now = datetime.datetime.now()

        myDict = collections.OrderedDict({
            "topic": 'TEMPER',
            "dateTime" : datetime.datetime.now().replace(microsecond=0).isoformat(),
            "device": deviceNumber,
            "location" : location,
            "temperature": round(temperatureF,1)
        })
        return json.dumps(myDict)

# ----------------------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------
class MessageHandler(object):
    def __init__(self, broker_address="mqttrv.local"):
        # self.local_broker_address = ''
        self.broker_address = broker_address
        self.client = mqtt.Client(client_id="", clean_session=True, userdata=None)

    # ---------------------------------------------------------------------
    def on_connect(self, client, userdata, flags, rc):
        logging.info('Connected to the MQTT broker!')
        pass

    # ---------------------------------------------------------------------
    def on_message(self, client, userdata, message):
        logging.warning('Not expecting inbound messages')

    def start(self):
        logging.debug('Message handling start - v4')
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        logging.debug('Start - connecting to ', self.broker_address)
        self.client.connect(self.broker_address)
        # self.client.subscribe(self.doorStatusTopic,0)
        self.client.loop_start()

    def cleanup(self):
        # self.client.unsubscribe(self.doorStatusTopic)
        self.client.disconnect()
        self.client.loop_stop()

    def send_info(self, json_data):
        #logging.DEBUG('Sending System Status Info on 'NODE' topic!')
        data = {}
        self.client.publish('TEMPER', json_data, qos=0)


# -----------------------------------------------------------------------------------------------
def discover_mqtt_host():
    from zeroconf import ServiceBrowser, Zeroconf
    host = None
    info = None

    def on_service_state_change(zeroconf, service_type, name, state_change):
        pass

    zeroconf = Zeroconf()
    browser = ServiceBrowser(zeroconf, "_mqtt._tcp.local.", handlers=[on_service_state_change])

    i = 0
    while not host:
        time.sleep(0.1)
        if browser.services:
            service = list(browser.services.values())[0]
            info = zeroconf.get_service_info(service.name, service.alias)
            ##print('info', info)
            ##print('info.server', info.server)
            host = socket.inet_ntoa(info.address)
        i += 1
        if i > 50:
            break
    zeroconf.close()
    try:
        return info.server, host
    except:
        pass
    return None


# -----------------------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------------------
if __name__ == '__main__':
    logging.warning("TemperUSB V0.1")
    logging.basicConfig(filename='/tmp/temperusb.log', level=logging.INFO)
    #logging.info('MQTTSystemInfo v2.1 [signal_strength]')
    #logging.info('Multicast DNS Service Discovery for Python Browser test')

    try:
        host = sys.argv[1]
        mqtt_broker_address = sys.argv[1]
    except:
        logging.warning( 'No host passed in on command line. Trying mDNS' )
        logging.warning('Attempting to find mqtt broker via mDNS')

    try:
        deviceNum = sys.argv[2]
    except:
        logging.warning( 'No device name passed in on command line. Will be device 1' )
        deviceNum = 1

    try:
        location = sys.argv[3]
    except:
        logging.warning( 'No location passed in on command line. Will be UNKNOWN' )
        location = 'UNKNOWN'

    try:
        tempOffset = float( sys.argv[4] )
    except:
        logging.warning( 'No temperature correction passed in on command line. Will be 0.0' )
        tempOffset = 0.0

        
    if (mqtt_broker_address is None):
        #
        host = discover_mqtt_host()
        if (host is not None):
            mqtt_broker_address = host[0]
            logging.info( 'Found MQTT Broker using mDNS on {}.{}'.format(host[0], host[1]))
        else:
            logging.warning('Unable to locate MQTT Broker using DNS')
            try:
                mqtt_broker_address = sys.argv[1]
            except:
                logging.critical('mDNS failed and no MQTT Broker address passed in via command line. Exiting')
                sys.exit(1)

    logging.warning('Connecting to {}'.format(mqtt_broker_address))
    m = MessageHandler(broker_address=mqtt_broker_address)
    m.start()

    temper = Temper()

    while True:
        for device in temper.devices:
            tempc = temper.getTemperature(device)
            tempf = (tempc * 9/5) + 32
            tempf += tempOffset;
            
            #devicebus = device.bus
            #deviceaddress = device.address

            #print(temper.asJSON(deviceNum, location, tempf))
            m.send_info(temper.asJSON(deviceNum, location, tempf))
        time.sleep(60)
