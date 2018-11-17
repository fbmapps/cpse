#!/bin/bash

##########
# Shell ScripT to start the python collector
#########

while true
do
   echo 'Starting Telemetry'
    /pyenvs/ftdtelem/env/bin/python /pyenvs/ftdtelem/app/collector_asr01.py
  sleep 10
done 
