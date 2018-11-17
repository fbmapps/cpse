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
import logging
from pyfiglet import Figlet
from halo import Halo
from logging.handlers import RotatingFileHandler 

######################################
#
# VARS AND ARRAYS
#
######################################

inside_array = []
outside_array = []

IFX_DATA_POINT = []
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
handler = RotatingFileHandler('asr_coll.log',maxBytes=5000000,backupCount=2)
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
    banner = figlet.renderText('COLL_DATA')
    print(banner)
    print("[+] 2018 the Worker www.cisco.com\n")


def ClearAllArray():
    inside_array = []
    outside_array = []

    IFX_DATA_POINT = []
    _DATA_POINT_ARRAY = []

    total_output_drops = 0
    input_pkts_ps = 0
    input_bits_ps
    input_bytes = 0
    input_pkts = 0
    input_error = 0

    output_pkts_ps = 0
    output_bits_ps
    output_bytes = 0
    output_pkts = 0
    output_error = 0


    logger.info('All Arrays are cleared out') 
    return None

def DataRetrieval(**device):
    '''
    Data Retrieval from Devices
    Input Device dictionary
    Returns None
    '''

    try:
        spinner.start(text='Connecting to {} for data Telemetry'.format(device['hostname']))
        #Connect to Devices
        #Open Connection
        logger.info('Data Retrieval started for {} '.format(device['hostname'])) 
        #Use PXSSH to Open Connection
        child = pxssh.pxssh()
        child.login(device['ipaddr'], device['user'], device['pasw'], auto_prompt_reset=False)
        child.expect('#')
        
        #Ask for WAN Side Interface Counters
        child.sendline('show int G0/0/0 | i put')
        child.expect('#')
        outside_data = child.before

        #Ask for LAN Side Interface Counters
        child.sendline('show int Po1 | i put')
        child.expect('#')
        inside_data = child.before

        #Close Connection
        child.logout()

        #Assigns Output to arrays
        #WAN
        for item in str(cpu_data.decode('utf-8')).splitlines():
            wan_array.append(item.lstrip())

        #LAN
        for item in str(mem_data.decode('utf-8')).splitlines():
            lan_array.append(item.lstrip())


        spinner.succeed(text='Telemetry collection is completed for {}'.format(device['hostname']))
        logger.info('Telemetry collection is completed for {}'.format(device['hostname']))

    except Exception as e:
        logger.error('Failed to pull data from {} '.format(device['hostname']) ,  exc_info=True)
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
    dpoint["time"] = str(datetime.utcnow())

    #Only in use when building IFX datapoint
    if kpi.startswith('ifx_'):
        k = kpi.split('_')
        dpoint["tags"]["flowdir"] = k[2]
        dpoint["tags"]["interface"] = k[1]
        dpoint["measurement"] = k[3]
    else:
        dpoint["measurement"] = kpi

    #Value
    dpoint["fields"]["value"] = value

    #Attach to Datapoint
    datapoint.append(dpoint)

    #Attach Job to Master DataPoint Array
    return None

def DataParser(**devices):
    '''
    Wrapper, for Easy Code Reading and SOLID
    '''
    
    #Erasing all Arrays at once
    ClearAllArray()
    
    try: 
        logger.info('Data Parsing started for {} '.format(device['hostname'])) 
        spinner.start(text='Parsing {} data Telemetry'.format(device['hostname']))

        #Interfaces Processing
        _IFXDataParser("inside",inside_array,**device)
        _IFXDataParser("outside",outside_array,**device)
        #_INTDataParser(internal_array,**device)

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


def _IFXDataParser(ifname,_array,**device):
    '''
    Take each Array and Transform it on Data write_points
    Input **device
    Return None
    '''
    #DATA
    # In the Array [0] always has the actual Command
    # [1] to [n] is the actual data
    #Data Parser
    regex = r"(\d+)"
    #Process CLI Outputs
    #drops
    _values = ','.join(re.findall(regex,_array[3]))
    _value_point = _values.split(',')

    total_output_drops =  int(_value_point[4])
    kpi = "ifx_{0}_drops".format(ifname)
    _DataPointBuilder(total_output_drops,kpi,IFX_DATA_POINT,**device)

   
    #INPUT Counters
    _values = ','.join(re.findall(regex,_array[5]))
    _value_point = _values.split(',')

    #bits/secs
    input_bits_ps = int(_value_point[1])
    kpi = "ifx_{0}_IN_bits-Rate".format(ifname)
    _DataPointBuilder(input_bits_ps,kpi,IFX_DATA_POINT,**device)

    #packets/sec
    input_packets_ps = int(_value_point[2])
    kpi = "ifx_{0}_IN_pkts-Rate".format(ifname)
    _DataPointBuilder(input_bits_ps,kpi,IFX_DATA_POINT,**device)

    #Total Input Traffic    
    _values = ','.join(re.findall(regex,_array[7]))
    _value_point = _values.split(',')

    input_packets = int(_value_point[0])
    kpi = "ifx_{0}_IN_pkts".format(ifname)
    _DataPointBuilder(input_pkts,kpi,IFX_DATA_POINT,**device)

    #Traffic Entering the Interface
    input_bytes = int(_value_point[0])
    kpi = "ifx_{0}_IN_bytes".format(ifname)
    _DataPointBuilder(input_bytes,kpi,IFX_DATA_POINT,**device)

    
    #Errors    
    _values = ','.join(re.findall(regex,_array[8]))
    _value_point = _values.split(',')

    input_error = int(_value_point[0])
    kpi = "ifx_{0}_IN_error".format(ifname)
    _DataPointBuilder(input_error,kpi,IFX_DATA_POINT,**device)



    #OUTPUT Counters
    _values = ','.join(re.findall(regex,_array[6]))
    _value_point = _values.split(',')

    #bits/secs
    output_bits_ps = int(_value_point[1])
    kpi = "ifx_{0}_OUT_bits-Rate".format(ifname)
    _DataPointBuilder(output_bits_ps,kpi,IFX_DATA_POINT,**device)

    #packets/sec
    output_packets_ps = int(_value_point[2])
    kpi = "ifx_{0}_OUT_pkts-Rate".format(ifname)
    _DataPointBuilder(output_bits_ps,kpi,IFX_DATA_POINT,**device)

    #Total OUTPUT Traffic    
    _values = ','.join(re.findall(regex,_array[10]))
    _value_point = _values.split(',')

    output_packets = int(_value_point[0])
    kpi = "ifx_{0}_OUT_pkts".format(ifname)
    _DataPointBuilder(output_pkts,kpi,IFX_DATA_POINT,**device)

    #Traffic Leaving the Interface
    output_bytes = int(_value_point[0])
    kpi = "ifx_{0}_OUT_bytes".format(ifname)
    _DataPointBuilder(input_bytes,kpi,IFX_DATA_POINT,**device)

    
    #Errors    
    _values = ','.join(re.findall(regex,_array[8]))
    _value_point = _values.split(',')

    output_error = int(_value_point[0])
    kpi = "ifx_{0}_OUT_error".format(ifname)
    _DataPointBuilder(output_error,kpi,IFX_DATA_POINT,**device)


    logger.info(IFX_DATA_POINT)
    _DATA_POINT_ARRAY.append(IFX_DATA_POINT)

    #KPI Formats
    #kpi ="ifx_{0}_IN_PktsPS-1m".format(ifname)

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
    asr01 = {}
    asr01['user'] = ''
    asr01['pasw'] = ''
    asr01['ipaddr'] = ''
    asr01['hostname'] = ''
    asr01['site'] = ''
    asr01['prompt'] = ''
    
    #Time Series Database Dictionary
    tsdb = {}
    tsdb['ipaddr']= '127.0.0.1' #Docker Image
    tsdb['port'] = 8086
    tsdb['user']=''
    tsdb['pasw']=''
    tsdb['dbname'] = 'asr01_telemetry'
    tsdb['datapoints'] = _DATA_POINT_ARRAY

    devices = []
    devices.append(asr01)

   #Proccess
    try:
        logger.info('Starting Data Collection proccess')
        print_banner()
        spinner = Halo(spinner='dots')

        for device in devices:
            spinner.start(text='Start Telemetry to {}'.format(device['hostname']))
            DataRetrieval(**device)
            time.sleep(1)
            DataParser(**device)
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
