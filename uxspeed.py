import pexpect
from pexpect import pxssh
import re
import requests
from influxdb import InfluxDBClient
import time
from datetime import datetime
import io
from pprint import pprint
from elasticsearch import Elasticsearch


import os
import sys
from subprocess import check_output, STDOUT
import logging
from pyfiglet import Figlet
from halo import Halo
from logging.handlers import RotatingFileHandler

######################################
#
# VARS AND ARRAYS
#
######################################
ux_server = {}
ux_array = []
_value_point = []

UX_DATA_POINT = []
_DATA_POINT_ARRAY = []

TIME_WAIT = 45

#####################################
#
#   LOGGER CONFIGURATION
#
#####################################

#Initialize the Logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

#Create a File handler
handler = RotatingFileHandler('clux.log',maxBytes=5000000,backupCount=2)
handler.setLevel(logging.DEBUG)

#set a format
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

# add the handlers to the logger
logger.addHandler(handler)

####################################
#
# Functions
#
####################################
def print_banner():
    '''
    Print a Welcome Banner
    '''
    os.system('clear')
    figlet =  Figlet(font='slant')
    banner = figlet.renderText('CLUX_DATA')
    print(banner)
    print("[+] 2018 the Worker www.cisco.com\n")


def ClearAllArray():
    ux_array = []
    _value_point = []

    UX_DATA_POINT = []
    _DATA_POINT_ARRAY = []

    last_ux_ping = 0
    last_ux_download = 0
    last_ux_upload = 0
    ux_server['id'] = '3221' #Server Triara (Merida, Mexico)
    ux_server['name'] = 'Triara (Merida, Mexico)'



    logger.info('All Arrays are cleared out')
    return None

def DataRetrieval():
    '''
    Data Retrieval from SpeedTest - CLI
    Input: None
    Returns None
    '''

    try:
        spinner.start(text='Connecting to {} for UX Telemetry'.format(ux_server['name']))
        #Connect to Devices
        #Open Connection
        logger.info('UX Data Retrieval started using {} '.format(ux_server['name']))

        #Use Speedtest-cli to Check UX
        ux_command = ['speedtest-cli', '--simple', '--server', '{}'.format(ux_server['id'])]
        ux_data = check_output(ux_command, stderr=STDOUT).decode('utf-8')

        for item in ux_data.splitlines():
            ux_array.append(item.lstrip())

        spinner.succeed(text='UX Telemetry collection is completed for {}'.format(ux_server['name']))
        logger.info('UX Telemetry collection is completed for {}'.format(ux_server['name']))

    except Exception as e:
        logger.error('Failed to pull data from {} '.format(ux_server['name']) ,  exc_info=True)
        raise

    return None

def _DataPointBuilder(value,kpi,datapoint,**device):

    '''
    DRY Helper function to build consistent Datapoints
    input
    returns None
    '''

    ipaddr = device['ipaddr']
    hostname = device['hostname']
    site = device['site']

    dpoint = {}
    dpoint["tags"] = {}
    dpoint["fields"] = {}

    #Standard Info for DP
    dpoint["tags"]["host"] = ipaddr
    dpoint["tags"]["hostname"] = hostname
    dpoint["tags"]["site"] = site
    dpoint["tags"]["server"] = ux_server['name']
    dpoint["time"] = str(datetime.utcnow())
    dpoint["measurement"] = kpi

    #Value
    dpoint["fields"]["value"] = value

    #Attach to Datapoint
    datapoint.append(dpoint)

    #Attach Job to Master DataPoint Array
    return None

def DataParser(**device):
    '''
    Wrapper, for Easy Code Reading and SOLID
    '''

    #Erasing all Arrays at once
    ClearAllArray()

    try:
        logger.info('UX Data Parsing started')
        spinner.start(text='Parsing UX data Telemetry')

        #UX Data Parsing
        _UXDataParser(ux_array,**device)

        spinner.succeed(text='Telemetry parsing is completed for {}'.format(device['hostname']))
        logger.info('Telemetry parsing is completed for {}'.format(device['hostname']))
    except Exception as e:
       logger.error('Data parsing failed for {}'.format(device['hostname']), exc_info=True)

    return None

def DataWriter(**tsdb):
    '''
    Write Data Points in TSDB
    INPUT SERVER DATA & DATAPOINTS
    RETURN NONE
    '''

    TSBD_HOST = tsdb['ipaddr']
    TSBD_PORT = tsdb['port']
    TSBD_USER = tsdb['user']
    TSBD_PASW = tsdb['pasw']
    TSDB_DB = tsdb['dbname']
    TSDB_DATAPOINTS = tsdb['datapoints']

    spinner.start(text='Writing Telemetry Data in DB for {}'.format(device['hostname']))


    #Check if Time Series Database exist if not create it
    logger.info('Check TSDB status')
    checkTSDB = _Check_TSDB_Status(**tsdb)

    if checkTSDB is False:
        logger.error('TSDB Checks failed. Not DATA has been written in DB')
        return None
    else:
       logger.info('TSDB Checked sucessfully!!!')


    try:
        logger.info('Starting TSDB Datapoint storage')
        client = InfluxDBClient(TSBD_HOST,
                                TSBD_PORT,
                                TSBD_USER,
                                TSBD_PASW,
                                TSDB_DB)

        #Write Data Point
        for item in TSDB_DATAPOINTS:
            logger.info('writing datapoint {}'.format(item))
            client.write_points(item)
            time.sleep(1)

        spinner.succeed(text='Data writing completed for {}'.format(device['hostname']))
        client.close()
        logger.info('Data writing completed for {}'.format(device['hostname']))
    except  Exception as e:
        logger.error('Datapoints writing failed' , exc_info=True)
        raise

    ClearAllArray()
    return None


def _UXDataParser(_array,**device):
    '''
    Take each Array and Transform it on Data write_points
    Input
    Return None
    '''
    #DATA
    # In the Array [0] is PING
    # [1] IS Download
    # [2] is Upload

    #Data Parser
    regex = r"(\d+\.\d+)"

    #Process CLI Outputs
    #ping
    _values = ','.join(re.findall(regex,_array[0]))
    _value_point = _values.split(',')

    last_ux_ping =  float(_value_point[0])
    kpi = "ux_ping_ms"
    _DataPointBuilder(last_ux_ping,kpi,UX_DATA_POINT,**device)


    #Download
    _values = ','.join(re.findall(regex,_array[1]))
    _value_point = _values.split(',')

    last_ux_download =  float(_value_point[0])
    kpi = "ux_download_mbps"
    _DataPointBuilder(last_ux_download,kpi,UX_DATA_POINT,**device)





    #Upload
    _values = ','.join(re.findall(regex,_array[2]))
    _value_point = _values.split(',')

    last_ux_upload =  float(_value_point[0])
    kpi = "ux_upload_mbps"
    _DataPointBuilder(last_ux_upload,kpi,UX_DATA_POINT,**device)



    #UX Index
    # A kpi to create a concrete way to measure the perception
    # of user in the event
    # Reference:
    # Wireless in Real Life Conditions:
    # 802.11b MAX 6mbps Downstream
    # 802.11g MAX 20Mbps Downstream
    # 802.11n MAX 100Mbps Downstream
    # 802.11ac MAX 200Mbps Downstream
    # Formulae:
    # SpeedTest Download / Wireless Index <= 1

    dot11b = 6
    dot11g = 20
    dot11n = 100
    dot11ac = 200

    if last_ux_download <= dot11b:
        ux_index = last_ux_download / dot11b
    elif last_ux_download > dot11b and last_ux_download <= dot11g:
        ux_index = last_ux_download / dot11g
    elif last_ux_download > dot11g and last_ux_download <= dot11n:
        ux_index = last_ux_download / dot11n
    else:
        #Is an dot11ac client
        ux_index = last_ux_download / dot11ac

    kpi = "ux_index"
    _DataPointBuilder(ux_index,kpi,UX_DATA_POINT,**device)


    logger.info(UX_DATA_POINT)
    _DATA_POINT_ARRAY.append(UX_DATA_POINT)


    return None


def _Check_TSDB_Status(**tsdb):

    '''Check if TSDB exist if not then create it'''

    try:
        logger.info('Checking TSDB {}'.format(tsdb['dbname']))
        client = InfluxDBClient(tsdb['ipaddr'], tsdb['port'], tsdb['user'], tsdb['pasw'])
        dblist = client.get_list_database()
        db_found = False
        for db in dblist:
            if db['name'] == tsdb['dbname']:
                logger.info('TSDB {} found'.format(tsdb['dbname']))
                db_found = True
        if not(db_found):
            logger.info('Creating TSDB {}'.format(tsdb['dbname']))
            client.create_database(tsdb['dbname'])
            logger.info('TSDB {} created sucessfully!!'.format(tsdb['dbname']))
        client.close()
        return True
    except Exception as e:
        logger.error('TSDB {} check fails'.format(tsdb['dbname']), exc_info=True)
        return False

if __name__ == '__main__':

    #Device in Dict Format to ease reading
    uxdevice = {}
    uxdevice['user'] = 'kraken'
    uxdevice['pasw'] = ''
    uxdevice['ipaddr'] = '10.0.114.251'
    uxdevice['hostname'] = 'UX_WIRELESS_TESTER'
    uxdevice['site'] = 'NOC WIRELESS NETWORK'
    uxdevice['prompt'] = ''

    #Time Series Database Dictionary
    tsdb = {}
    tsdb['ipaddr']= '127.0.0.1' #Docker Image
    tsdb['port'] = 8086
    tsdb['user']=''
    tsdb['pasw']=''
    tsdb['dbname'] = 'asr01_telemetry'
    tsdb['datapoints'] = _DATA_POINT_ARRAY

    devices = []
    devices.append(uxdevice)

    ux_server['id'] = '3221' #Server Triara (Merida, Mexico)
    ux_server['name'] = 'Triara (Merida, Mexico)'

   #Proccess
    try:
        logger.info('Starting UX Data Collection proccess')
        print_banner()
        spinner = Halo(spinner='dots')

        for device in devices:
            spinner.start(text='Start UX Telemetry to {}'.format(device['hostname']))
            DataRetrieval()
            time.sleep(1)
            DataParser(**device)
            #pprint(UX_DATA_POINT)
            time.sleep(.5)

        DataWriter(**tsdb)

        spinner.succeed(text='Telemetry Collection has finished' )
        logger.info('Telemetry collection has finished')
    except KeyboardInterrupt:
        logger.error('User Clear process')
        raise
    except Exception as e:
        logger.error('Telemetry Collection fails' , exc_info=True)
        raise
