# -*- coding: utf-8 -*-
"""
Created on Mon Jun  5 12:10:23 2023

@author: thobson
This version is desinged to work with an Arduino UNO microcontroller connected over LAN
Arduino must be loaded with the sketch 'EthernetReceiveSendBinary4_0.ino'
Microcontroller will send/receive bytes from an RS9000 Orbit Shaker,
connected via the (female) RS232 port
"""

import requests
from os import path
import csv
import PySimpleGUI as sg
from time import sleep, time
from datetime import date
from datetime import datetime
import pandas as pd


#------------------------------Fixed Values------------------------------------

devaddr = 40 # Address of the Orbit Shaker, 40 is the default, but should be shown on startup
IP_addr = "138.253.143.253" # IP address of the mictrocontroller on LAN network (can be changed in sketch)
sg.theme('SystemDefault')

#------------------------Initialised Parameters--------------------------------

dflt_ramp_file_path = "C:/Users/workstation/Documents/Demonstration 2023-10-05/Orbit_Shaker_Default_Ramp_CS.csv"

dflt_ramp = 2.0     # Default slow ramp rate in RPM per min

cs_str = '-1'
dr_str = '-1'

proc_status = "Manual"
error_str = 'No errors'
timer_started = False
timer_stopped = False
al_sounded = False

stirr_on = False
heat_on = False
sound_sh_on = False
sound_m_on = False
sound_l_on = False

on_off = 0  # Initially set to 0 as byte defined by adding

first_heat = False
first_stirr = False
first_both = True

logs_on = False
logs_started = False
segs = 1
log_step_size = 60.0    # The time period (in s) over which process parameters are logged

t_set = 0    # Temperature setpoint in degrees C
t_ramp_set = 0     # Temperature ramp rate in deg C per min


a_speed_set = 0       # Agitation speed in RPM
a_ramp_set = 0      # Agitation speed ramp in minutes to setpoint

dwell_time = 0
ramp_time = 0
ramp_1_0_time = 0
step_num = 0

steps_s = []
steps_r = []

#--------------------------Limiting Parameters-------------------------------

t_set_max = 150
t_ramp_max = 9
a_speed_max = 600 
a_ramp_max = 5.0      # Max agitation speed to be set durectly, larger values require stepping

#-------------------------------Tolerances------------------------------------

max_wait = 3.0 # Time (in s) application will wait for response when reading/writing values before timing out
agit_tol = 1.0 # Value below setpoint (in RPM) at which timer will start
temp_tol = 1.0 # Value below setpoint (in C) at which timer will start

#--------------------------RAM Addresses---------------------------------------

# All addresses can be used for read or write operations, if used in Comm_Read and Comm_Write respectively

ram_HS_OnOff = 33

ram_errors = 34

ram_temp_high = 36  # RAM address for temperature setpoint
ram_temp_low = 37
ram_temp_ramp = 38  # RAM address for temperature ramp

ram_agit_high = 41  # RAM address for speed setpoint
ram_agit_low = 42
ram_agit_ramp = 43  # RAM address for speed ramp

ram_temp_meas_read_high = 39    # RAM address for temperature measurement
ram_temp_meas_read_low = 40

ram_agit_meas_read_high = 44    # # RAM address for speed measurement
ram_agit_meas_read_low = 45

ram_heat_pow = 48




#------------------------Heater, Stirrer & Sounder On/Off----------------------

def OnOff_Bin(stirrer_on, heater_on, sound_short_on, sound_med_on, sound_long_on):

    on_off_byte = 0
    
    if (stirrer_on == True):
        on_off_byte += 2
    if (heater_on == True):
        on_off_byte += 4
    if (sound_short_on == True):
        on_off_byte += 64
    if (sound_med_on == True):
        on_off_byte += 128  
    if (sound_long_on == True):
        on_off_byte += 192
    
    return(on_off_byte)

def OnOff_Bin_Read(on_off_bin):

    if ((on_off_bin % 8) == 0):
        heat_on = 'Off'
        stirr_on = 'Off'
    if ((on_off_bin % 8) == 2):
        heat_on = 'Off'
        stirr_on = 'On'
    if ((on_off_bin % 8) == 4):
        heat_on = 'On'
        stirr_on = 'Off'
    if ((on_off_bin % 8) == 6):
        heat_on = 'On'
        stirr_on = 'On'

    return heat_on, stirr_on

#-------------------------Error Interpretation Function----------------------------

def Err_Bin_Read(err_bin):

    if (err_bin == 0):
        err_string = 'No Errors'
    else:
        err_string = ''
        if ((err_bin % 16) == 8):
            err_string = err_string + 'Excessive RPM; '
        if ((err_bin % 32) >= 16):
            err_string = err_string + 'Internal temp probe shorted; '
        if ((err_bin % 64) >= 32):
            err_string = err_string + 'Internal temp probe disconnected; '
        if ((err_bin % 128) >= 64):
            err_string = err_string + 'External temp probe error; '
        if (err_bin >= 128):
            err_string = err_string + 'Motor high current error; '

    return err_string

#-------------------------Temp Setpoint and Ramp Write----------------------------

def Temp_Set_Bin(temp_set):       # Translates the user input temperature values into binary values needed to send commands

    temp_set_hex = hex(int(temp_set*10))
    print (temp_set_hex)
    if (len(temp_set_hex) > 3):
        temp_set_hex_low = "0x"+temp_set_hex[-2:]
    else:
        temp_set_hex_low = "0x"+temp_set_hex[-1:]
    print(temp_set_hex_low)
    
    if (len(temp_set_hex) == 6):
        temp_set_hex_high = "0x"+temp_set_hex[-4:-2]
    if (len(temp_set_hex) == 5):
        temp_set_hex_high = "0x"+temp_set_hex[-3:-2]
    if (len(temp_set_hex) <= 4):
        temp_set_hex_high = "0x0"
        
    # print(temp_set_hex_high)
    
    temp_set_dec_low = int(temp_set_hex_low, 16)
    temp_set_dec_high = int(temp_set_hex_high, 16)
    
    print(temp_set_dec_high)
    print(temp_set_dec_low)

    return(temp_set_dec_high, temp_set_dec_low)

def Temp_Set_Ramp_Bin(temp_ramp_set):   # Translates the user input temp ramp value into binary to send as command
    
    temp_ramp_set_dec = int(temp_ramp_set*10)
    print(temp_ramp_set_dec)
    
    return(temp_ramp_set_dec)


#-------------------------Temp Setpoint, Meas and Ramp Read-----------------------

def Temp_Bin_Read(temp_bin_high, temp_bin_low):       # Translates binary values read from machine into temperature values to be displayed (reverse of 'Temp_Set_Bin')

    temp_high_hex = hex(temp_bin_high)
    temp_low_hex = hex(temp_bin_low)

##    print('Temp high hex: '+temp_high_hex)
    
    if (temp_bin_high == 0):
        temp_hex = temp_low_hex
    elif(len(temp_low_hex)<4):
        temp_hex = "0x"+temp_high_hex[-((len(temp_high_hex)-2)):]+"0"+temp_low_hex[-((len(temp_low_hex)-2)):] # Necessary to prevent eg. 0x104 reading as 0x14
    else:
        temp_hex = "0x"+temp_high_hex[-((len(temp_high_hex)-2)):]+temp_low_hex[-((len(temp_low_hex)-2)):]       # Strips the 2 characters '0x' from the high and low hexadecimal strings and concatenates them

##    print('Temp hex high: '+temp_high_hex[-((len(temp_high_hex)-2)):])
##    print('Temp hex low: '+temp_low_hex[-((len(temp_low_hex)-2)):])
##    print('Temp hex: '+temp_hex)
    
    temp_meas_dec = int(temp_hex, 16)
    temp_result = float(temp_meas_dec)/10                                                                              

    return(temp_result)


#-------------------------Speed Setpoint and Ramp------------------------------

def Agit_Set_Bin(agit_speed_set):     # Translates the user input speed values into binary values needed to send commands

    agit_speed_hex = hex(int(agit_speed_set))
    print ('Speed Hex: '+str(agit_speed_hex))
    if (len(agit_speed_hex) > 3):
        agit_speed_hex_low = "0x"+agit_speed_hex[-2:]
    else:
        agit_speed_hex_low = "0x"+agit_speed_hex[-1:]
    print("Speed Hex Low: "+str(agit_speed_hex_low))
    
    if (len(agit_speed_hex)== 6):
        agit_speed_hex_high = "0x"+agit_speed_hex[-4:-2]
    if (len(agit_speed_hex) == 5):
        agit_speed_hex_high = "0x"+agit_speed_hex[-3:-2]
    if (len(agit_speed_hex) <= 4):
        agit_speed_hex_high = "0x0"
        
    print("Speed Hex High: "+str(agit_speed_hex_high))
    
    agit_speed_dec_low = int(agit_speed_hex_low, 16)
    agit_speed_dec_high = int(agit_speed_hex_high, 16)

    print("Speed Dec Low: "+str(agit_speed_dec_low))
    print("Speed Dec High: "+str(agit_speed_dec_high))

    return(agit_speed_dec_high,agit_speed_dec_low)

def Agit_Set_Ramp_Bin(agit_ramp_set):   # Translates the user input speed ramp value into binary to send as command
    
    agit_ramp_set_dec = int(agit_ramp_set*10)
    
    return(agit_ramp_set_dec)

#---------------------Agit Setpoint, Meas and Ramp Read-------------------------

def Agit_Bin_Read(agit_bin_high, agit_bin_low):     # Translates binary values read from machine into speed values to be displayed (reverse of 'Agit_Set_Bin')

    agit_high_hex = hex(agit_bin_high)
    agit_low_hex = hex(agit_bin_low)


    if (agit_bin_high == 0):
        agit_hex = agit_low_hex
    elif (len(agit_low_hex)<4):
        agit_hex = "0x"+agit_high_hex[-((len(agit_high_hex)-2)):]+"0"+agit_low_hex[-((len(agit_low_hex)-2)):]   # Necessary to prevent eg. 0x104 reading as 0x14
    else:
        agit_hex = "0x"+agit_high_hex[-((len(agit_high_hex)-2)):]+agit_low_hex[-((len(agit_low_hex)-2)):]

    
    agit_meas_dec = int(agit_hex, 16)
    agit_result = float(agit_meas_dec)      # These values not being divided by 10 is the only actual difference to the function 'Temp_Bin_Read'                                                                              

    return(agit_result)

def Heat_Pow_Bin_Read(heat_bin):

    per = round(((float(heat_bin)/255)*100),0)

    return per


#-----------------------Send/Receive Functions----------------------------------

def Comm_Write(dvaddr, ramaddr, datbyte): # Function to write commands to RS9000 and confirm

    payload = {'dv': str(devaddr), 'rv':str(ramaddr), 'dtv':str(datbyte)} # Define the values to send to the microcontroller            
    r2 = requests.post('http://'+IP_addr+'/post', params = payload) # This is the line that sends the command values over the network

    HTML_string = r2.text # Makes a string of the HTML code in the request
    
    sub_ind1 = HTML_string.index("""id="cs""") # Finds where checksum (cs) is first defined in HTML
    cs_sub_string = HTML_string[sub_ind1:HTML_string.index("><br>", sub_ind1)] # Takes out the substring where the cs value is defined
    # print(cs_sub_string) # Uncomment for debugging
    cs_str = cs_sub_string[-(len(cs_sub_string)-24):] # Substring will contain 24 characters then the value, these last characters are the cs value
    

    sub_ind2 = HTML_string.index("""id="dr""") # Finds where data read (dr) is first defined in HTML
    dr_sub_string = HTML_string[sub_ind2:HTML_string.index("><br>", sub_ind2)] # Takes out the substring where the dr value is defined
    # print(dr_sub_string) # Uncomment for debugging
    dr_str = dr_sub_string[-(len(dr_sub_string)-24):] # Substring will contain 24 characters then the value, these last characters are the dr value
    

    return (cs_str, dr_str)

def Comm_Read(dvaddr, ramaddr): # Function to read values from RS9000 and confirm

    payload = {'dv': str(devaddr), 'rv':str(ramaddr+128)} # 128 is always added to RAM addresses for reading, as machine interprets highest bit of '1' as read operation           
    r2 = requests.post('http://'+IP_addr+'/post', params = payload) # This is the line that sends the command values over the network

    HTML_string = r2.text # Makes a string of the HTML code in the request
    
    sub_ind1 = HTML_string.index("""id="cs""") # Finds where checksum (cs) is first defined in HTML
    cs_sub_string = HTML_string[sub_ind1:HTML_string.index("><br>", sub_ind1)] # Takes out the substring where the cs value is defined
    # print(cs_sub_string) # Uncomment for debugging
    cs_str = cs_sub_string[-(len(cs_sub_string)-24):] # Substring will contain 24 characters then the value, these last characters are the cs value
    

    sub_ind2 = HTML_string.index("""id="dr""") # Finds where data read (dr) is first defined in HTML
    dr_sub_string = HTML_string[sub_ind2:HTML_string.index("><br>", sub_ind2)] # Takes out the substring where the dr value is defined
    # print(dr_sub_string) # Uncomment for debugging
    dr_str = dr_sub_string[-(len(dr_sub_string)-24):] # Substring will contain 24 characters then the value, these last characters are the dr value
    

    return (cs_str, dr_str)

#----------------------------Simple Byte Reading Functions -----------------------

def One_Byte_Read(dvaddr,ram_addr): # Simple function to read the data byte of a given address
            chks_str = '-1'
            datr_str = '-1'
        
            chks_str, datr_str = Comm_Read(devaddr, ram_addr)  # Reads the current speed to take as starting point for ramping
            byte_read = int(datr_str)
            
            return(byte_read)


def Two_Byte_Read(dvaddr,ram_high,ram_low): # Same as above, but for reading the high and low bytes of a parameter
            chks_str = '-1'
            datr_str = '-1'
        
            chks_str, datr_str = Comm_Read(devaddr, ram_high)  # Reads the current speed to take as starting point for ramping
            byte_high = int(datr_str)
        
            chks_str, datr_str = Comm_Read(devaddr, ram_low)
            byte_low = int(datr_str)
            
            return(byte_high,byte_low)

#---------------------------Log Saving Function--------------------------------


def Save_Logs(l_dict,l_headings,time_list,temp_sp_list,temp_m_list,speed_sp_list,speed_m_list,\
              heat_pow_list,stirr_stat_list,err_stat_list,proc_stat_list):
    
            l_dict[l_headings[0]] = time_list
            l_dict[l_headings[1]] = temp_sp_list
            l_dict[l_headings[2]] = temp_m_list
            l_dict[l_headings[3]] = speed_sp_list
            l_dict[l_headings[4]] = speed_m_list
            l_dict[l_headings[5]] = heat_pow_list
            l_dict[l_headings[6]] = stirr_stat_list
            l_dict[l_headings[7]] = err_stat_list
            l_dict[l_headings[8]] = proc_stat_list

            df_log = pd.DataFrame(l_dict,columns=l_headings)

            log_file_path = 'C:/Data/RS9000_Out_Files/'
            log_file_name = 'Logs_'+str(date.today())+'_'+str(datetime.now().strftime('%H%M%S')+'.csv')

            log_file = df_log.to_csv((log_file_path+log_file_name),index=False,sep=',',columns=l_headings)

            print('Logs saved at: '+log_file_path+log_file_name)


#-------------------Full Setting Functions Including Checks---------------------

def Set_On_Off(str_on, ht_on, snd_sh_on, snd_m_on, snd_l_on, daddr, rm_HS_OnOff, mx_wait):

        on_off = OnOff_Bin(str_on, ht_on, snd_sh_on, snd_m_on, snd_l_on)
        # print (on_off)

        cs_str = '-1'

        t_0 = time()        # Starts a counter for timeout if the command is not received
        
        while (cs_str == '-1'):

            print('Writing On/Off command')

            cs_str, dr_str = Comm_Write(daddr, rm_HS_OnOff, on_off) # Write commands to RS9000 and confirm

            print('On/Off write Checksum = '+cs_str)
           # print('Data byte = '+dr_str)

            if ((time() - t_0) > mx_wait):     # Loop will time out if no response after 5 seconds

               print('No response received, timed out. Check RS9000 is connected')

               break

        cs_str = '-1'

        t_0 = time()        # Starts a counter for timeout if the command is not received
        
        while (cs_str == '-1'):
            
            print('Reading On/Off command')
            
            cs_str, dr_str = Comm_Read(daddr, rm_HS_OnOff) # Read values from RS9000 and confirm

            print('On/Off read Checksum = '+cs_str)
            print('On/Off read Data byte = '+dr_str)

            if ((time() - t_0) > mx_wait):     # Loop will time out if no response after 5 seconds

               print('No response received, timed out. Check RS9000 is connected')

               break

##        if (int(dr_str) == on_off):        
##            print("On/Off settings confirmed")

def Temp_Set(t_set, max_wait):

        temp_set_bytes = Temp_Set_Bin(t_set) # Function returns array with two values, the high and low bytes
        temp_set_byte_high = temp_set_bytes[0]
        temp_set_byte_low = temp_set_bytes[1]
##        print ('Temp set byte high: '+str(temp_set_byte_high)) # For debugging
##        print ('Temp set byte low: '+str(temp_set_byte_low))

        dr_str = '-1'
        
        while (int(dr_str) != temp_set_byte_high):      # This loop will run until the setting as read from the machine matches the intended setting
        
            cs_str = '-1'

            t_0 = time()        # Starts a counter for timeout if the command is not received
            
            while (cs_str == '-1'):     # This loop runs until it is confirmed that the command was received (i.e. positive 'checksum' value)

                print('Attempting to write temp high')
                cs_str, dr_str = Comm_Write(devaddr, ram_temp_high, temp_set_byte_high) # Function to write commands to RS9000 and confirm
                print('Checksum = '+cs_str)
                print('Data byte = '+dr_str)

                if ((time() - t_0) > max_wait):     # Loop will time out if no response after 5 seconds

                    print('No response received, timed out. Check RS9000 is connected')

                    break            

            cs_str = '-1'

            t_0 = time()        # Starts a counter for timeout if the command is not received
            
            while (cs_str == '-1'):
                
                print('Attempting to read temp high')
                cs_str, dr_str = Comm_Read(devaddr, ram_temp_high) # Function to read commands to RS9000 and confirm
                print('Checksum = '+cs_str)
                print('Data byte = '+dr_str)

                if ((time() - t_0) > max_wait):     # Loop will time out if no response after 5 seconds

                    print('No response received, timed out. Check RS9000 is connected')

                    break
            if ((time() - t_0) > max_wait):     # If the write attempt timed out, the loop is also broken

                break            

        if (int(dr_str) == temp_set_byte_high):
            print('Temp set high confirmed')

        dr_str = '-1'
        
        while (int(dr_str) != temp_set_byte_low):

            cs_str = '-1'

            t_0 = time()        # Starts a counter for timeout if the command is not received
            
            while (cs_str == '-1'):
                
                print('Attempting to write temp low')
                cs_str, dr_str = Comm_Write(devaddr, ram_temp_low, temp_set_byte_low) # Repeat for temp byte low
                print('Checksum = '+cs_str)
                print('Data byte = '+dr_str)

                if ((time() - t_0) > max_wait):     # Loop will time out if no response after 5 seconds

                    print('No response received, timed out. Check RS9000 is connected')

                    break

            cs_str = '-1'

            t_0 = time()        # Starts a counter for timeout if the command is not received
            
            while (cs_str == '-1'):
                
                print('Attempting to read temp low')
                cs_str, dr_str = Comm_Read(devaddr, ram_temp_low) # Repeat for temp byte low
                print('Checksum = '+cs_str)
                print('Data byte = '+dr_str)

                if ((time() - t_0) > max_wait):     # Loop will time out if no response after 5 seconds

                    print('No response received, timed out. Check RS9000 is connected')

                    break

            if ((time() - t_0) > max_wait):     # If the write attempt timed out, the loop is also broken

                break
                

        if (int(dr_str) == temp_set_byte_low):        
            print('Temp set low confirmed')

def Temp_Ramp_Set(t_ramp_set, max_wait):
        temp_ramp_set_byte = Temp_Set_Ramp_Bin(t_ramp_set)

        dr_str = '-1'
        
        while (int(dr_str) != temp_ramp_set_byte):
                    
            cs_str = '-1'
            
            t_0 = time()        # Starts a counter for timeout if the command is not received
            
            while (cs_str == '-1'):

                print('Attempting to write temp ramp')


                cs_str, dr_str = Comm_Write(devaddr, ram_temp_ramp, temp_ramp_set_byte) # Write commands to RS9000 and confirm
                print('Checksum = '+cs_str)
                print('Data byte = '+dr_str)

                if ((time() - t_0) > max_wait):     # If the write attempt timed out, the loop is also broken
                    print('No response received, timed out. Check RS9000 is connected')
                    break

            cs_str = '-1'

            t_0 = time()        # Starts a counter for timeout if the command is not received
            
            while (cs_str == '-1'):

                print('Attempting to read temp ramp')

                cs_str, dr_str = Comm_Read(devaddr, ram_temp_ramp)
                print('Checksum = '+cs_str)
                print('Data byte = '+dr_str)

                if ((time() - t_0) > max_wait):     # If the write attempt timed out, the loop is also broken
                    print('No response received, timed out. Check RS9000 is connected')
                    break
            if ((time() - t_0) > max_wait):     # If the write attempt timed out, the loop is also broken
                
                break

            if (int(dr_str) == temp_ramp_set_byte):
                print('Temp ramp set confirmed')

def Speed_Set(a_speed_set, max_wait):

        print('Speed setting: '+str(a_speed_set)+' RPM')
        
        agit_speed_set_bytes = Agit_Set_Bin(a_speed_set)
        agit_speed_set_byte_high = agit_speed_set_bytes[0]
        agit_speed_set_byte_low = agit_speed_set_bytes[1]

        dr_str = '-1'
        
        while (int(dr_str) != agit_speed_set_byte_high):

            cs_str = '-1'
            t_0 = time()        # Starts a counter for timeout if the command is not received
                
            while (cs_str == '-1'):
                    
                print('Writing agit high')

                cs_str, dr_str = Comm_Write(devaddr, ram_agit_high, agit_speed_set_byte_high) # Function to write commands to RS9000 and confirm
                print('Agit high write Checksum = '+cs_str)
                print('Agit high write Data byte = '+dr_str)

                if ((time() - t_0) > max_wait):     # If the write attempt timed out, the loop is also broken
                    print('No response received, timed out. Check RS9000 is connected')
                    break

            cs_str = '-1'
            t_0 = time()        # Starts a counter for timeout if the command is not received
                
            while (cs_str == '-1'):
                    
                print('Reading agit high')

                cs_str, dr_str = Comm_Read(devaddr, ram_agit_high) # Function to read commands to RS9000 and confirm
                print('Agit high read Checksum = '+cs_str)
                print('Agit high read Data byte = '+dr_str)

                if ((time() - t_0) > max_wait):     # If the write attempt timed out, the loop is also broken
                    print('No response received, timed out. Check RS9000 is connected')
                    break

            if ((time() - t_0) > max_wait):     # If the write attempt timed out, the loop is also broken
                
                break

        if (int(dr_str) == agit_speed_set_byte_high):        
            print('Speed set high confirmed at '+str(agit_speed_set_byte_high))

        dr_str = '-1'
        
        while (int(dr_str) != agit_speed_set_byte_low):
            

            cs_str = '-1'
            t_0 = time()        # Starts a counter for timeout if the command is not received
                
            while (cs_str == '-1'):

                print('Writing agit low')

                cs_str, dr_str = Comm_Write(devaddr, ram_agit_low, agit_speed_set_byte_low) # Repeat for speed byte low
                print('Agit low write Checksum = '+cs_str)
                print('Agit low write Data byte = '+dr_str)

                if ((time() - t_0) > max_wait):     # If the write attempt timed out, the loop is also broken
                    print('No response received, timed out. Check RS9000 is connected')
                    break

            cs_str = '-1'
            t_0 = time()        # Starts a counter for timeout if the command is not received
                
            while (cs_str == '-1'):

                print('Reading agit low')

                cs_str, dr_str = Comm_Read(devaddr, ram_agit_low) # Repeat for temp byte low
                print('Agit low read Checksum = '+cs_str)
                print('Agit low read Data byte = '+dr_str)

                if ((time() - t_0) > max_wait):     # If the write attempt timed out, the loop is also broken
                    print('No response received, timed out. Check RS9000 is connected')
                    break

            if ((time() - t_0) > max_wait):     # If the write attempt timed out, the loop is also broken
                
                break

        if (int(dr_str) == agit_speed_set_byte_low):        
            print('Speed set low confirmed at '+str(agit_speed_set_byte_low))

def Set_Speed_Ramp(a_ramp_set, max_wait):

        agit_ramp_set_byte = Agit_Set_Ramp_Bin(a_ramp_set)

        dr_str = '-1'
        
        while (int(dr_str) != agit_ramp_set_byte):

            cs_str = '-1'
            t_0 = time()        # Starts a counter for timeout if the command is not received
                
            while (cs_str == '-1'):


                cs_str, dr_str = Comm_Write(devaddr, ram_agit_ramp, agit_ramp_set_byte) # Function to write commands to RS9000 and confirm
                print('Agit ramp write Checksum = '+cs_str)
                print('Agit ramp write Data byte = '+dr_str)

                if ((time() - t_0) > max_wait):     # If the write attempt timed out, the loop is also broken
                    print('No response received, timed out. Check RS9000 is connected')
                    break
                
            cs_str = '-1'
            t_0 = time()        # Starts a counter for timeout if the command is not received
            

            while (cs_str == '-1'):    

                cs_str, dr_str = Comm_Read(devaddr, ram_agit_ramp) # Read values to check
                print('Agit ramp read Checksum = '+cs_str)
                print('Agit ramp read Data byte = '+dr_str)

                if ((time() - t_0) > max_wait):     # If the write attempt timed out, the loop is also broken
                    print('No response received, timed out. Check RS9000 is connected')
                    break

            if ((time() - t_0) > max_wait):     # If the write attempt timed out, the loop is also broken

                break

        if (int(dr_str) == agit_ramp_set_byte):        
            print('Speed ramp set confirmed at '+str(agit_ramp_set_byte))

#-------------------Function to Generate List of Speed Setpoints and Ramps-------------
            
def Get_Ramp_List(steps_s,steps_r,a_speed_0,a_speed_set,a_ramp_set,dwell_time_sp):
    if (a_speed_set <= a_speed_max):
    
        if (a_ramp_set <= a_ramp_max):
            steps_s.append(a_speed_set)
            steps_r.append(a_ramp_set)
        else:           # Allows for ramp times longer than the maximum allowed by the system (9 mins) by breaking ramp down into multiple steps
            seg_num = (a_ramp_set/a_ramp_max)
            print('segnum: '+str(seg_num))
            speed_step = ((a_speed_set-a_speed_0)/seg_num)
            print('Speed step: '+str(speed_step))
            seg_rem = seg_num - float(int(seg_num))
            print('segrem: '+str(seg_rem))
            if (seg_rem == 0):      # if the interval is a multiple of the max ramp, no fractional step is used
                segs = int(seg_num)
                for i in range(1,(segs+1)):     # Makes a list of the temperature setpoint steps and the ramps to be used for each (all max ramp bar the last step)
                    print('Step: '+str(round(((speed_step*float(i))+a_speed_0),0)))
                    steps_s.append(round(((speed_step*float(i))+a_speed_0),0))
                    steps_r.append(a_ramp_max)
            else:       # If the interval is not a multiple of the max ramp, and additional, fractional step is included at the end
                segs = int(seg_num)+1
                for i in range(1,segs):     # Makes a list of the temperature setpoint steps and the ramps to be used for each (all max ramp bar the last step)
                    print('Step: '+str(round(((speed_step*float(i))+a_speed_0),0)))
                    steps_s.append(round(((speed_step*float(i))+a_speed_0),0))
                    steps_r.append(a_ramp_max)
                steps_s.append(a_speed_set)
                steps_r.append(round((a_ramp_max*seg_rem),0))   # These manage the last step of the ramp which will usually be some fraction of max ramp
        
        steps_r[-1] = steps_r[-1] + round(dwell_time_sp,0)    # If a dwell time at sp1 is specified, this is added to the last ramp time in the current list (not a new list element)    
    
        step_num = 1
    
    else:
        step_num = 0
    
    return steps_s, steps_r, step_num

#----------------------------Dialog Box Functions------------------------------

def Menu_Dialog():
    
    line0_0 = sg.Text("BIGMAP WP4 RS9000 Control Application",font=('Arial Bold',12))
    line0_1 = sg.Text("Please Select Function")
    b0_1 = sg.Button("Process Setup",key='-SETUP-', button_color='navy')
    b0_2 = sg.Button("Manual Control",key='-MANUAL-', button_color='navy')
    b0_3 = sg.Button("Quit",key='-QUIT-', button_color='navy')
    
    layout_0 = [[line0_0],[line0_1],[b0_1,b0_2],[b0_3]]
    
    window_0 = sg.Window("Orbit Shaker Control Application BIGMAP WP4", layout_0, size=(350,150))
    
    while True:
        event, values = window_0.read() # 'window0' was defined in the dialog box setup
        
        if (event == '-SETUP-'):
            print("Running process setup")
            Process_Setup_Dialog()
            
        if (event == '-MANUAL-'):
            print("Running manual control")
            Manual_Control_Dialog(stirr_on, heat_on, sound_sh_on, sound_m_on, sound_l_on, devaddr, ram_HS_OnOff, max_wait)
        
        
        if ((event == '-QUIT-') or (event == sg.WINDOW_CLOSED)):
            break
        
    window_0.close()

def Manual_Control_Dialog(stirr_on, heat_on, sound_sh_on, sound_m_on, sound_l_on, devaddr, ram_HS_OnOff, max_wait):

    line0 = sg.Text("Manual On/Off Options",font=('Arial Bold',16))
    
    l01 = sg.Button("Stirrer Off",key='-STIRROFF-', button_color=('navy', 'white'))
    l02 = sg.Button("Heater Off", key='-HEATOFF-', button_color=('navy', 'white'))
    l03 = sg.Button("Sounder Off", key = '-SOUNDOFF-', button_color=('navy', 'white'))
    
    b01 = sg.Button("Stirrer On", key='-STIRRON-', button_color='navy')
    b02 = sg.Button("Heater On", key='-HEATON-', button_color='navy')
    b011 = sg.Button("Sounder Short", key='-SOUNDSHRT-', button_color='navy')
    b012 = sg.Button("Sounder Medium", key = '-SOUNDMED-', button_color='navy')
    b013 = sg.Button("Sounder Long", key='-SOUNDLONG-', button_color='navy')
    
    line10 = sg.Text('Manual Process Parameters',font=('Arial Bold',16))
    
    line1 = sg.Text("Enter temperature setpoint in C, (0.1 C precision)", key='-OUT-',expand_x=True, justification='left')
    box1 = sg.Input('', enable_events=True,key='-INPUT1-', expand_x=True, justification='left')
    
    line2 = sg.Text("Enter temperature ramp in C per min, (0.1 C precision)", key='-OUT-',expand_x=True, justification='left')
    box2 = sg.Input('', enable_events=True,key='-INPUT2-', expand_x=True, justification='left')
    
    line3 = sg.Text("Enter speed setpoint in RPM, (1 RPM precision)", key='-OUT-',expand_x=True, justification='left')
    box3 = sg.Input('', enable_events=True,key='-INPUT3-', expand_x=True, justification='left')
    
    line4 = sg.Text("Enter speed ramp in minues to setpoint, (0.1 minute precision)", key='-OUT-',expand_x=True, justification='left')
    box4 = sg.Input('', enable_events=True,key='-INPUT4-', expand_x=True, justification='left')
    
    send_a_1 = sg.Button("Send", key='-SENDONOFF-', button_color='navy')
    send_b_1 = sg.Button("Send Temp Set", key='-SENDTS-', button_color='navy')
    send_b_2 = sg.Button("Send Temp Ramp", key='-SENDTR-', button_color='navy')
    send_b_3 = sg.Button("Send Stirr Set", key='-SENDSS-', button_color='navy')
    send_b_4 = sg.Button("Send Stirr Ramp", key='-SENDSR-', button_color='navy')
    
    back_b = sg.Button("Back", key='-BACK-',button_color='navy')
    end_b = sg.Button("Finish", key='-FINISH-', button_color='navy')
    
    layout_1 = [[line0],\
              [l01,b01],[l02,b02],[l03,b011,b012,b013],\
              [send_a_1],\
              [],\
              [line10],\
              [line1],[box1,send_b_1],\
              [line2],[box2,send_b_2],\
              [line3],[box3,send_b_3],\
              [line4],[box4,send_b_4],\
              [back_b,end_b]]
        
    window_1 = sg.Window("Orbit Shaker Manual Control", layout_1, size=(750,600))
    
    while True:
        event, values = window_1.read() # 'window1' was defined in the dialog box setup
        
        if (event == '-STIRROFF-'):
            window_1['-STIRROFF-'].update(button_color=('navy','white')) # These are to toggle the appearance of the buttons to match the commands
            window_1['-STIRRON-'].update(button_color=('white','navy'))
            stirr_on = False
        if (event == '-STIRRON-'):
            stirr_on = True
            window_1['-STIRRON-'].update(button_color=('navy','white'))
            window_1['-STIRROFF-'].update(button_color=('white','navy'))
    
        if (event == '-HEATOFF-'):
            window_1['-HEATOFF-'].update(button_color=('navy','white'))
            window_1['-HEATON-'].update(button_color=('white','navy'))
            heat_on = False
        if (event == '-HEATON-'):
            window_1['-HEATON-'].update(button_color=('navy','white'))
            window_1['-HEATOFF-'].update(button_color=('white','navy'))
            heat_on = True
            
        if (event == '-SOUNDOFF-'):
            window_1['-SOUNDOFF-'].update(button_color=('navy','white'))
            window_1['-SOUNDSHRT-'].update(button_color=('white','navy'))
            window_1['-SOUNDMED-'].update(button_color=('white','navy'))
            window_1['-SOUNDLONG-'].update(button_color=('white','navy'))
            sound_sh_on = False
            sound_m_on = False
            sound_l_on = False
        if (event == '-SOUNDSHRT-'):
            window_1['-SOUNDSHRT-'].update(button_color=('navy','white'))
            window_1['-SOUNDOFF-'].update(button_color=('white','navy'))
            window_1['-SOUNDMED-'].update(button_color=('white','navy'))
            window_1['-SOUNDLONG-'].update(button_color=('white','navy'))
            sound_sh_on = True
            sound_m_on = False
            sound_l_on = False
        if (event == '-SOUNDMED-'):
            window_1['-SOUNDMED-'].update(button_color=('navy','white'))
            window_1['-SOUNDOFF-'].update(button_color=('white','navy'))
            window_1['-SOUNDSHRT-'].update(button_color=('white','navy'))
            window_1['-SOUNDLONG-'].update(button_color=('white','navy'))
            sound_m_on = True
            sound_sh_on = False
            sound_l_on = False
        if (event == '-SOUNDLONG-'):
            window_1['-SOUNDLONG-'].update(button_color=('navy','white'))
            window_1['-SOUNDOFF-'].update(button_color=('white','navy'))
            window_1['-SOUNDSHRT-'].update(button_color=('white','navy'))
            window_1['-SOUNDMED-'].update(button_color=('white','navy'))
            sound_l_on = True
            sound_sh_on = False
            sound_m_on = False
            
        if (event == '-SENDONOFF-'): # This sends the settings to the microcontroller to send to orbit shaker
    
            Set_On_Off(stirr_on, heat_on, sound_sh_on, sound_m_on, sound_l_on, devaddr, ram_HS_OnOff, max_wait)
        
        if (event == "-SENDTS-"):
            print("Temp setpoint = "+values["-INPUT1-"]+" C")
            if (values['-INPUT1-'] != ''):  # Sets value only if field is not empty, if field empty, stays at 0
                t_set = float(values["-INPUT1-"])
    
            Temp_Set(t_set, max_wait)            # Translates intended values into binary commands, sends to RS9000 and checks receipt
           
        if (event == "-SENDTR-"):
            print("Temp ramp = "+values["-INPUT2-"]+" C/min")
            if (values['-INPUT2-'] != ''):
                t_ramp_set = float(values["-INPUT2-"])
                
            Temp_Ramp_Set(t_ramp_set, max_wait)
                       
        if (event == "-SENDSS-"):
            print("Stirrer speed = "+values["-INPUT3-"])
            if (values['-INPUT3-'] != ''):
                a_speed_set = float(values["-INPUT3-"])
                
            Speed_Set(a_speed_set, max_wait)
            
        if (event == "-SENDSR-"):
            print("Stirrer ramp = "+values["-INPUT4-"])
            if (values['-INPUT4-'] != ''):
                a_ramp_set = float(values["-INPUT4-"])
    
            Set_Speed_Ramp(a_ramp_set, max_wait)
            
        if (event == '-FINISH-'):
            Process_Monitor_Dialog(steps_s,steps_r,segs,step_num,first_both,first_stirr,first_heat,\
                               heat_on,stirr_on,timer_started,timer_stopped,\
                               proc_status,ramp_1_0_time,logs_on,logs_started)
            break
        
        if ((event == '-BACK-') or (event == sg.WIN_CLOSED)):
            break
        
    window_1.close()

def Process_Setup_Dialog():

    line2_0 = sg.Text("Set up Process",font=('Arial Bold',16))
    
    line_brwse = sg.Text("Select input file (if using)", key='-OUT-',expand_x=True, justification='left')
    box_brwse = sg.Input(key = '-FINPUT-')
    b_brwse = sg.FileBrowse('Browse', key='-BROWSE-')
    
    b_fill = sg.Button("Fill",key='-FILL-',button_color='navy')
    
    b_dflt = sg.Button("Use Default Ramp",key='-DFLT-',button_color=('navy','white'))
    
    line2_1 = sg.Text("Temperature setpoint in C, (0.1 C precision)                        ", key='-OUT-',expand_x=True, justification='left')
    box2_1 = sg.Input('', enable_events=True,key='-INPUT2_1-', expand_x=True, justification='left')
    line2_2 = sg.Text("Temperature ramp to setpoint in C per min, (0.1 C precision)", key='-OUT-',expand_x=True, justification='left')
    box2_2 = sg.Input('', enable_events=True,key='-INPUT2_2-', expand_x=True, justification='left')
    line2_3 = sg.Text("Dwell time at temp setpoint in mins, (0.1 precision)             ", key='-OUT-',expand_x=True, justification='left')
    box2_3 = sg.Input('', enable_events=True,key='-INPUT2_3-', expand_x=True, justification='left')
    
    line2_4 = sg.Text("Stirrer setpoint 1 in RPM, (1 RPM precision)                      ", key='-OUT-',expand_x=True, justification='left')
    box2_4 = sg.Input('', enable_events=True,key='-INPUT2_4-', expand_x=True, justification='left')
    line2_5 = sg.Text("Stirrer ramp to setpoint 1 in minutes, (0.1 min precision)     ", key='-OUT-',expand_x=True, justification='left')
    box2_5 = sg.Input('', enable_events=True,key='-INPUT2_5-', expand_x=True, justification='left')
    
    line2_8 = sg.Text("Dwell time at stirr setpoint 1 in mins, (0.1 precision)           ", key='-OUT-',expand_x=True, justification='left')
    box2_8 = sg.Input('', enable_events=True,key='-INPUT2_6-', expand_x=True, justification='left')
    
    line2_6 = sg.Text("Stirrer setpoint 2 in RPM, (1 RPM precision)                      ", key='-OUT-',expand_x=True, justification='left')
    box2_6 = sg.Input('', enable_events=True,key='-INPUT2_7-', expand_x=True, justification='left')
    line2_7 = sg.Text("Stirrer ramp to setpoint 2 in minutes, (0.1 min precision)     ", key='-OUT-',expand_x=True, justification='left')
    box2_7 = sg.Input('', enable_events=True,key='-INPUT2_8-', expand_x=True, justification='left')
    
    line2_9 = sg.Text("(Dwell time for stirrer will be matched to temp dwell)", key='-OUT-',expand_x=True, justification='left')
    
    line2_10 = sg.Text("Start order for heating and stirring", font=('Arial Bold',14))
    b2_10 = sg.Button("Heater First",key='-HEAT1ST-', button_color='navy')
    b2_11 = sg.Button("Stirrer First", key='-STIRR1ST-', button_color='navy')
    b2_12 = sg.Button("Same Time", key = '-BOTH1ST-', button_color=('navy', 'white'))
    
    start_b_2 = sg.Button("Start Process", key='-START2-', button_color='navy')
    end_b_2 = sg.Button("Back", key='-QUIT2-', button_color='navy')
    log_b_1 = sg.Button("Logging Off", key='-LOGOFF-',button_color=('navy', 'white'))
    log_b_2 = sg.Button("Logging On", key='-LOGON-',button_color='navy') 
    
    layout_2 = [[line2_0],\
              [],\
              [line_brwse,box_brwse,b_brwse],\
              [b_dflt,b_fill],\
              [line2_1,box2_1],\
              [line2_2,box2_2],\
              [line2_3,box2_3],\
              [],\
              [line2_4,box2_4],\
              [line2_5,box2_5],\
              [line2_8,box2_8],\
              [line2_6,box2_6],\
              [line2_7,box2_7],\
              [line2_9],\
              [],\
              [line2_10],\
              [b2_10, b2_11, b2_12],\
              [log_b_1,log_b_2],\
              [start_b_2],\
            
              [end_b_2]]
    
    window_2 = sg.Window("Orbit Shaker Process Setup", layout_2, size=(750,520))
    
    dflt_ramp_on = True

    first_heat = False
    first_stirr = False
    first_both = True
    
    while True:
        event, values = window_2.read() # 'window2' was defined in the dialog box setup
        
        if ((event == '-DFLT-') and (dflt_ramp_on == True)):
            window_2['-DFLT-'].update(button_color=('white','navy'))
            dflt_ramp_on = False
        elif ((event == '-DFLT-') and (dflt_ramp_on == False)):
            window_2['-DFLT-'].update(button_color=('navy','white'))
            dflt_ramp_on = True
    
        if (event == '-HEAT1ST-'):
            window_2['-HEAT1ST-'].update(button_color=('navy','white'))
            window_2['-STIRR1ST-'].update(button_color=('white','navy'))
            window_2['-BOTH1ST-'].update(button_color=('white','navy'))
            first_heat = True
            first_stirr = False
            first_both = False
        if (event == '-STIRR1ST-'):
            window_2['-STIRR1ST-'].update(button_color=('navy','white'))
            window_2['-HEAT1ST-'].update(button_color=('white','navy'))
            window_2['-BOTH1ST-'].update(button_color=('white','navy'))
            first_heat = False
            first_stirr = True
            first_both = False
        if (event == '-BOTH1ST-'):
            window_2['-BOTH1ST-'].update(button_color=('navy','white'))
            window_2['-HEAT1ST-'].update(button_color=('white','navy'))
            window_2['-STIRR1ST-'].update(button_color=('white','navy'))
            first_heat = False
            first_stirr = False
            first_both = True
    
        if (event == '-LOGON-'):
            logs_on = True
            window_2['-LOGON-'].update(button_color=('navy','white'))
            window_2['-LOGOFF-'].update(button_color=('white','navy'))
    
        if (event == '-LOGOFF-'):
            logs_on = False
            window_2['-LOGOFF-'].update(button_color=('navy','white'))
            window_2['-LOGON-'].update(button_color=('white','navy'))
            
        if (event == '-FILL-'):
            

            if (dflt_ramp_on == True):
                inp_list = []
                try:
                    with open(dflt_ramp_file_path,encoding = 'utf-8-sig') as csvfile:   # First inserts the default ramp values (will also do this if not input file is selected)
                        reader=csv.reader(csvfile, delimiter = ',')
                        for row in reader:
                            inp_list.append(row[1]) # Makes a list of the default ramp values reading from default file
                except:
                    sg.popup("No suitable default ramp parameters file found, please try again or swtich off default ramp")
                    print("No suitable default ramp parameters file found, please try again or swtich off default ramp")

            else:
                inp_list = ['0']*10
            
            if (path.exists(values['-FINPUT-']) == True):
                
                if (values['-FINPUT-'][-4:]=='.csv'):
                
                    inp_file_path = values['-FINPUT-']
    
                            
                    with open(inp_file_path,encoding = 'utf-8-sig') as csvfile:     # Then inserts the max speed and temp from the user-selected file
                        reader=csv.reader(csvfile, delimiter = ',')
                        k = 0
                        for row in reader:
                            if (k == 1):
                                try:
                                    inp_list[2] = row[3]    # Temp setpoint
                                    inp_list[8] = row[4]    # Speed setpoint
                                    inp_list[4] = row[5]    # Dwell time
                                
                                    inp_list[9] = str(int(((float(inp_list[8]) - float(inp_list[5]))/dflt_ramp)))     # Calculates ramp based on default value
                                    print("Stirr 1: "+str(inp_list[5]))
                                    print("Stirr 2: "+str(float(row[4])))
                                    print("Ramp 2: "+str(inp_list[9]))
                                    
                                except:
                                    sg.popup("File does not match expected format, default values only are used, ramp to final stirr speed could not be calculated")
                                    print("File does not match expected format, default values only are used, ramp to final stirr speed could not be calculated")
                                    
                                break                   # Only second line needs to be read
                            k = k + 1
                else:
                    sg.popup("Please select a CSV file")
                        
            if (inp_list[0] =='Heater'):
                window_2['-HEAT1ST-'].update(button_color=('navy','white'))
                window_2['-STIRR1ST-'].update(button_color=('white','navy'))
                window_2['-BOTH1ST-'].update(button_color=('white','navy'))
                first_heat = True
                first_stirr = False
                first_both = False
                
            if (inp_list[0] =='Stirrer'):
                window_2['-STIRR1ST-'].update(button_color=('navy','white'))
                window_2['-HEAT1ST-'].update(button_color=('white','navy'))
                window_2['-BOTH1ST-'].update(button_color=('white','navy'))
                first_heat = False
                first_stirr = True
                first_both = False
                
            if (inp_list[0] =='Both'):
                window_2['-BOTH1ST-'].update(button_color=('navy','white'))
                window_2['-HEAT1ST-'].update(button_color=('white','navy'))
                window_2['-STIRR1ST-'].update(button_color=('white','navy'))
                first_heat = False
                first_stirr = False
                first_both = True
                
            if (inp_list[1] =='On'):
                logs_on = True
                window_2['-LOGON-'].update(button_color=('navy','white'))
                window_2['-LOGOFF-'].update(button_color=('white','navy'))
                
            if (inp_list[1] =='Off'):
                logs_on = False
                window_2['-LOGOFF-'].update(button_color=('navy','white'))
                window_2['-LOGON-'].update(button_color=('white','navy'))
                
            for j in range(2,10):   # Populates the input fields with the parameters from the defaults file
                window_2['-INPUT2_'+str(j-1)+'-'].update(inp_list[j])
                                      
            
    
        if (event == '-START2-'):
    
            if (values['-INPUT2_1-'] != ''):
                t_set = float(values['-INPUT2_1-'])
            else:
                t_set = 0
            print(t_set)
            if (values['-INPUT2_2-'] != ''):
                t_ramp_set = float(values["-INPUT2_2-"])
            else:
                t_ramp_set = 0
            print(t_ramp_set)
            if (values['-INPUT2_3-'] != ''):
                dwell_time = float(values['-INPUT2_3-'])
            else:
                dwell_time = 0
            print(dwell_time)
            if (values['-INPUT2_4-'] != ''):
                a_speed_set = float(values["-INPUT2_4-"])
            else:
                a_speed_set = 0
            print(a_speed_set)
            if (values['-INPUT2_5-'] != ''):
                a_ramp_set = float(values["-INPUT2_5-"])
            else:
                a_ramp_set = 0
            print(a_ramp_set)
            if (values['-INPUT2_6-'] != ''):
                dwell_time_sp1 = float(values['-INPUT2_6-'])
            else:
                dwell_time_sp1 = 0
            if (values['-INPUT2_7-'] != ''):
                a_speed_set_2 = float(values["-INPUT2_7-"])
            else:
                a_speed_set_2 = 0
            print(a_speed_set)
            if (values['-INPUT2_8-'] != ''):
                a_ramp_set_2 = float(values["-INPUT2_8-"])
            else:
                a_ramp_set_2 = 0
            print(a_ramp_set)
            if ((values['-INPUT2_1-'] != '') and (values['-INPUT2_2-'] != '')):
                ramp_time = (t_set/t_ramp_set)
            else:
                ramp_time = 0
            print(ramp_time)
    
            if (t_set <= t_set_max):
                temp_set_bytes = Temp_Set_Bin(t_set) # Function returns array with two values, the high and low bytes
                temp_set_byte_high = temp_set_bytes[0]
                temp_set_byte_low = temp_set_bytes[1]
                
            if (t_ramp_set <= t_ramp_max):
                temp_ramp_set_byte = Temp_Set_Ramp_Bin(t_ramp_set)
    
            if (a_speed_set <= a_speed_max):
                agit_speed_set_bytes = Agit_Set_Bin(a_speed_set)
                agit_speed_set_byte_high = agit_speed_set_bytes[0]
                agit_speed_set_byte_low = agit_speed_set_bytes[1]
    
    
    
            if (t_set <= t_set_max):
                Temp_Set(t_set, max_wait)
                sleep(0.01) # 10 ms are left between each command as the RS9000 will be ready for a new command after 7 ms
    
            if (t_ramp_set <= t_ramp_max):
                Temp_Ramp_Set(t_ramp_set, max_wait)
                sleep(0.01)
                
            a_set_0_high, a_set_0_low = Two_Byte_Read(devaddr,ram_agit_meas_read_high,ram_agit_meas_read_low) # Reads the current speed to take as starting point for ramping
        
            if ((a_set_0_high != -1) and (a_set_0_low != -1)):
                a_speed_0 = float(Agit_Bin_Read(a_set_0_high, a_set_0_low))
            else:
                a_speed_0 = 0.0
    
            steps_s = []
            steps_r = []

            print('a_speed_0: '+str(a_speed_0))
            
            steps_s, steps_r, step_num = Get_Ramp_List(steps_s,steps_r,a_speed_0,a_speed_set,a_ramp_set,dwell_time_sp1) # Adds ramp steps to the provided list based on paramaters chosen

            print(steps_s)
            print(steps_r)
    
            print('a_speed_set: '+str(a_speed_set))
                    
            steps_s, steps_r, step_num = Get_Ramp_List(steps_s,steps_r,a_speed_set,a_speed_set_2,a_ramp_set_2,0)

            print(steps_s)
            print(steps_r)
    
            print("Speed Steps: "+str(steps_s))
            print("Speed Ramp Steps: "+str(steps_r))
            
            Speed_Set(steps_s[0], max_wait)
            sleep(0.01)
            Set_Speed_Ramp(steps_r[0], max_wait)
            sleep(0.01)
            
            stirr_on = False
            heat_on = False
            sound_sh_on = False
            sound_m_on = True
            sound_l_on = False
    
            if (first_heat == True):
                heat_on = True
                proc_status = 'RampHeat'
                Set_On_Off(stirr_on, heat_on, sound_sh_on, sound_m_on, sound_l_on, devaddr, ram_HS_OnOff, max_wait)
                sound_m_on = False
                ramp_1_0_time = time()      # This takes note of when the ramp was started, to ensure ramping is not faster than intended
    
                logs_started = False
                
                Process_Monitor_Dialog(steps_s,steps_r,segs,step_num,first_both,first_stirr,first_heat,\
                                   heat_on,stirr_on,dwell_time,timer_started,timer_stopped,\
                                    proc_status,ramp_1_0_time,logs_on,logs_started)
                sleep(0.01)
    
            elif (first_stirr == True):
                stirr_on = True
                proc_status = 'RampStirr'
                Set_On_Off(stirr_on, heat_on, sound_sh_on, sound_m_on, sound_l_on, devaddr, ram_HS_OnOff, max_wait)
                sound_m_on = False
                ramp_1_0_time = time()      # This takes note of when the ramp was started, to ensure ramping is not faster than intended
    
                logs_started = False
                
                Process_Monitor_Dialog(steps_s,steps_r,segs,step_num,first_both,first_stirr,first_heat,\
                                   heat_on,stirr_on,dwell_time,timer_started,timer_stopped,\
                                    proc_status,ramp_1_0_time,logs_on,logs_started)
                
                sleep(0.01)
                
            else:
                heat_on = True
                stirr_on = True
                proc_status = 'RampHeat&Stirr'
                Set_On_Off(stirr_on, heat_on, sound_sh_on, sound_m_on, sound_l_on, devaddr, ram_HS_OnOff, max_wait)
                sound_m_on = False
                ramp_1_0_time = time()      # This takes note of when the ramp was started, to ensure ramping is not faster than intended
    
                logs_started = False
                
                Process_Monitor_Dialog(steps_s,steps_r,segs,step_num,first_both,first_stirr,first_heat,\
                                   heat_on,stirr_on,dwell_time,timer_started,timer_stopped,\
                                   proc_status,ramp_1_0_time,logs_on,logs_started)
                
                sleep(0.01)
    
            
    
            break
    
    
    
        if (event == '-QUIT2-' or event == sg.WIN_CLOSED):
            break
    
    window_2.close()


def Process_Monitor_Dialog(steps_s,steps_r,segs,step_num,first_both,first_stirr,first_heat,\
                   heat_on,stirr_on,dwell_time,timer_started,timer_stopped,\
                   proc_status,ramp_1_0_time,logs_on,logs_started):

    line3_0 = sg.Text("Process Monitor Dashboard",font=('Arial Bold',16))
    
    line3_1 = sg.Text("Temperature setpoint in C", key='-OUT-', font=('Arial',14), expand_x=True, justification='left')
    box3_1 = sg.StatusBar('0', enable_events=True,key='-OUTPUT3_1-', font = ('Arial Bold', 18), text_color='lime', background_color='black', expand_x=True, justification='left')
    line3_2 = sg.Text("Measured Temperature in C", key='-OUT-', font=('Arial',14), expand_x=True, justification='left')
    box3_2 = sg.StatusBar('0', enable_events=True,key='-OUTPUT3_2-', font = ('Arial Bold', 18), text_color='lime', background_color='black', expand_x=True, justification='left')
    line3_3 = sg.Text("Stirrer setpoint in RPM", key='-OUT-', font=('Arial',14), expand_x=True, justification='left')
    box3_3 = sg.StatusBar('0', enable_events=True,key='-OUTPUT3_3-', font = ('Arial Bold', 18), text_color='lime', background_color='black', expand_x=True, justification='left')
    line3_4 = sg.Text("Measured stirrer speed in RPM", key='-OUT-', font=('Arial',14), expand_x=True, justification='left')
    box3_4 = sg.StatusBar('0', enable_events=True,key='-OUTPUT3_4-', font = ('Arial Bold', 18), text_color='lime', background_color='black', expand_x=True, justification='left')
    
    line3_5 = sg.Text("Heater power in %", key='-OUT-',font=('Arial',14), expand_x=True, justification='left')
    box3_5 = sg.StatusBar('0', enable_events=True,key='-OUTPUT3_5-', font = ('Arial Bold', 18), text_color='lime', background_color='black', expand_x=True, justification='left')
    
    line3_7 = sg.Text("Heater status (On/Off)", key='-OUT-',font=('Arial',14), expand_x=True, justification='left')
    box3_7 = sg.StatusBar('Off', enable_events=True,key='-OUTPUT3_7-', font = ('Arial Bold', 18), text_color='lime', background_color='black', expand_x=True, justification='left')
    line3_8 = sg.Text("Stirrer status (On/Off)", key='-OUT-',font=('Arial',14), expand_x=True, justification='left')
    box3_8 = sg.StatusBar('Off', enable_events=True,key='-OUTPUT3_8-', font = ('Arial Bold', 18), text_color='lime', background_color='black', expand_x=True, justification='left')
    
    line3_9 = sg.Text("Machine error status", key='-OUT-',font=('Arial',14), expand_x=True, justification='left')
    box3_9 = sg.StatusBar('No errors', enable_events=True,key='-OUTPUT3_9-', font = ('Arial Bold', 18), text_color='lime', background_color='black', expand_x=True, justification='left')
    
    line3_10 = sg.Text("Progress", key='-OUT-',font=('Arial',14), expand_x=True, justification='left')
    box3_10 = sg.StatusBar('Manual', enable_events=True,key='-OUTPUT3_10-', font = ('Arial Bold', 18), text_color='lime', background_color='black', expand_x=True, justification='left')
    
    
    
    stop_b_3 = sg.Button("Stop Process", key='-STOP3-', button_color='navy')
    
    end_b_3 = sg.Button("Exit", key='-QUIT3-', button_color='navy')
    
    layout_3 = [[line3_0],\
              [],\
              [line3_1,box3_1],\
              [line3_2,box3_2],\
              [line3_3,box3_3],\
              [line3_4,box3_4],\
              [],\
              [line3_5,box3_5],\
              [],\
              [line3_7,box3_7],\
              [line3_8,box3_8],\
              [line3_9,box3_9],\
              [line3_10,box3_10],\
              [],\
              [stop_b_3],\
            
              [end_b_3]]
    
    window_3 = sg.Window("Orbit Shaker Process Monitor", layout_3, size=(500,500))
    
    while True:
        event, values = window_3.read(timeout=1000) # 'window_3' was defined in the dialog box setup, timeout is time (in ms) before window refreshes
    
        time_0 = time()
    
        if ((logs_on == True) and (logs_started == False)):
            log_dict = {}
            log_headings = ['Time (s)','Temp Setpoint (C)','Temp Measured (C)','Speed Setpoint (RPM)','Speed Measured (RPM)',\
                            'Heater Power (%)','Stirrer Status (on/off)','Error Status','Process Status']
            
            times, temp_sps, temp_ms, speed_sps, speed_ms, heat_pows, stirr_stats, err_stats, proc_stats = [],[],[],[],[],[],[],[],[]
    
            log_0 = time()
            log_step_0 = time()
    
            logs_started = True
        
        temp_set_high, temp_set_low = Two_Byte_Read(devaddr,ram_temp_high,ram_temp_low) # Read the bytes for temperature setpoint
        if ((temp_set_high != -1) and (temp_set_low != -1)):
            temp_set_read = Temp_Bin_Read(temp_set_high, temp_set_low) # Translate the bytes into the temperature setpoint reading on the RS9000

        temp_meas_high, temp_meas_low = Two_Byte_Read(devaddr,ram_temp_meas_read_high,ram_temp_meas_read_low)
        if ((temp_meas_high != -1) and (temp_meas_low != -1)):
            temp_meas = Temp_Bin_Read(temp_meas_high, temp_meas_low)
            
        agit_set_high, agit_set_low = Two_Byte_Read(devaddr,ram_agit_high,ram_agit_low)
        if ((agit_set_high != -1) and (agit_set_low != -1)):
            agit_set_read = Agit_Bin_Read(agit_set_high, agit_set_low)
            
        agit_meas_high, agit_meas_low = Two_Byte_Read(devaddr,ram_agit_meas_read_high,ram_agit_meas_read_low)
        if ((agit_meas_high != -1) and (agit_meas_low != -1)):
            agit_meas_read = Agit_Bin_Read(agit_meas_high, agit_meas_low)
    
        heat_pow = One_Byte_Read(devaddr,ram_heat_pow)
        if (heat_pow != -1):
            heat_per = Heat_Pow_Bin_Read(heat_pow)
    
        on_off_val = One_Byte_Read(devaddr,ram_HS_OnOff)
        if (on_off_val != -1):
            heat_is_on, stirr_is_on = OnOff_Bin_Read(on_off_val)    
            
        err_byte = One_Byte_Read(devaddr,ram_errors)
        if (err_byte != -1):
            error_str = Err_Bin_Read(err_byte)
    
    
                
        window_3['-OUTPUT3_1-'].update(str(temp_set_read))
        window_3['-OUTPUT3_2-'].update(str(temp_meas))
        window_3['-OUTPUT3_3-'].update(str(agit_set_read))
        window_3['-OUTPUT3_4-'].update(str(agit_meas_read))
        window_3['-OUTPUT3_5-'].update(str(heat_per))
    
        window_3['-OUTPUT3_7-'].update(heat_is_on)
        window_3['-OUTPUT3_8-'].update(stirr_is_on)
        window_3['-OUTPUT3_9-'].update(error_str)
        window_3['-OUTPUT3_10-'].update(proc_status)
    
        if ((first_both == True) and (timer_started == False)):
            
            if ((agit_meas_read >= (agit_set_read-agit_tol)) and (agit_meas_read <= (agit_set_read+agit_tol)) and (((time()-ramp_1_0_time)/60)>steps_r[step_num-1])):
    
                
                if  (step_num == len(steps_s)):
                    print("Starting Timer (Setpoint 2)")
                    start_time = time()
                    timer_started = True
                    proc_status = "Timer Start"
                    window_3['-OUTPUT3_10-'].update(proc_status)
                    
                if (step_num < len(steps_s)):
                    print("Partial ramp step reached")
                    proc_status = "Speed step "+str(step_num+1)+"/"+str(len(steps_s))
                    window_3['-OUTPUT3_10-'].update(proc_status)
                    Set_Speed_Ramp(steps_r[step_num], max_wait)
                    print("Setting ramp to: "+str(steps_r[step_num]))
                    Speed_Set(steps_s[step_num], max_wait)
                    print("Setting speed to: "+str(steps_s[step_num]))
                    Set_On_Off(stirr_on, heat_on, sound_sh_on, sound_m_on, sound_l_on, devaddr, ram_HS_OnOff, max_wait)
                    ramp_1_0_time = time()
                    step_num=step_num+1
                
    
        if ((first_stirr == True) and (timer_started == False)):
        
            if ((agit_meas_read >= (agit_set_read-agit_tol)) and (agit_meas_read <= (agit_set_read+agit_tol)) and (heat_on == False) and (((time()-ramp_1_0_time)/60)>steps_r[step_num-1])):

                          
                if  ((step_num == len(steps_s)) and (heat_on == False)):
                    print("Starting Heater")
                    heat_on = True
                    Set_On_Off(stirr_on, heat_on, sound_sh_on, sound_m_on, sound_l_on, devaddr, ram_HS_OnOff, max_wait)
                    proc_status = "RampHeat"
                    window_3['-OUTPUT3_10-'].update(proc_status)
                    
                if ((step_num < len(steps_s)) and (heat_on == False)):
                    print("Partial ramp step reached")
                    proc_status = "Speed step "+str(step_num+1)+"/"+str(len(steps_s))
                    window_3['-OUTPUT3_10-'].update(proc_status)
                    Set_Speed_Ramp(steps_r[step_num], max_wait)
                    print("Setting ramp to: "+str(steps_r[step_num]))
                    Speed_Set(steps_s[step_num], max_wait)
                    print("Setting speed to: "+str(steps_s[step_num]))
                    Set_On_Off(stirr_on, heat_on, sound_sh_on, sound_m_on, sound_l_on, devaddr, ram_HS_OnOff, max_wait)
                    ramp_1_0_time = time()
                    step_num=step_num+1
                
    
            if((temp_meas >= (temp_set_read-temp_tol)) and (temp_meas <= (temp_set_read+agit_tol)) and (heat_on == True)):
    
                print("Starting Timer")
                start_time = time()
                timer_started = True
                proc_status = "Timer Start"
                window_3['-OUTPUT3_10-'].update(proc_status)
                
    
        if ((first_heat == True) and (timer_started == False)):
    
            if((temp_meas >= (temp_set_read-temp_tol)) and (temp_meas <= (temp_set_read+agit_tol)) and (stirr_on == False)):
    
                    print("Starting Stirrer")
                    stirr_on = True
                    Set_On_Off(stirr_on, heat_on, sound_sh_on, sound_m_on, sound_l_on, devaddr, ram_HS_OnOff, max_wait)
                    proc_status = "RampStirr"
                    window_3['-OUTPUT3_10-'].update(proc_status)
    
        
            if ((agit_meas_read >= (agit_set_read-agit_tol)) and (agit_meas_read <= (agit_set_read+agit_tol)) and (stirr_on == True) and (((time()-ramp_1_0_time)/60)>steps_r[step_num-1])):
                        
                if  ((step_num == len(steps_s)) and (stirr_on == True)):
                    print("Starting Timer")
                    start_time = time()
                    timer_started = True
                    proc_status = "Timer Start"
                    window_3['-OUTPUT3_10-'].update(proc_status)
                    
                if ((step_num < len(steps_s)) and (stirr_on == True)):
                    print("Partial ramp step reached")
                    proc_status = "Speed step "+str(step_num+1)+"/"+str(len(steps_s))
                    window_3['-OUTPUT3_10-'].update(proc_status)
                    Set_Speed_Ramp(steps_r[step_num], max_wait)
                    print("Setting ramp to: "+str(steps_r[step_num]))
                    Speed_Set(steps_s[step_num], max_wait)
                    print("Setting speed to: "+str(steps_s[step_num]))
                    Set_On_Off(stirr_on, heat_on, sound_sh_on, sound_m_on, sound_l_on, devaddr, ram_HS_OnOff, max_wait)
                    ramp_1_0_time = time()
                    step_num=step_num+1
                
    
        if ((timer_started == True) and (timer_stopped == False)):
            print("Time elapsed: "+str(round((time()-start_time),0))+" s")
            print("Time remaining: "+str(round((dwell_time*60)-(time()-start_time)))+" s")
            if ((round((dwell_time*60)-(time()-start_time))) >= 0):
                proc_status = str(round((dwell_time*60)-(time()-start_time)))
            else:
                heat_on = False
                stirr_on = False
                Set_On_Off(stirr_on, heat_on, sound_sh_on, sound_m_on, sound_l_on, devaddr, ram_HS_OnOff, max_wait)
                proc_status = "Finished"
                window_3['-OUTPUT3_10-'].update(proc_status)
                timer_stopped = True
    
        if ((logs_on == True) and (time()-log_step_0)>log_step_size):
    
            time_log = round((time()-log_0),1)
            
            print('Logged Parameters')
            print('Time (s): '+str(time_log))
            print('Temp Setpoint (C): '+str(temp_set_read))
            print('Temp Measured (C): '+str(temp_meas))
            print('Speed Setpoint (RPM): '+str(agit_set_read))
            print('Speed Measured (RPM): '+str(agit_meas_read))
            
            print('Heater Power (%): '+str(heat_per))
            print('Heater Status (on/off): '+str(heat_is_on))
            print('Stirrer Status (on/off): '+str(stirr_is_on))
            print('Error Status: '+str(error_str))
            print('Process Status: '+str(proc_status))
    
            times.append(str(time_log))
            temp_sps.append(str(temp_set_read))
            temp_ms.append(str(temp_meas))
            speed_sps.append(str(agit_set_read))
            speed_ms.append(str(agit_meas_read))
            heat_pows.append(str(heat_per))
            stirr_stats.append(str(stirr_is_on))
            err_stats.append(str(error_str))
            proc_stats.append(str(proc_status))
            
            log_step_0 = time()
    
    
        if ((error_str == 'Motor high current error; ') and (al_sounded == False)):

            sleep(1)
    
            if (logs_on == True):

                time_log = round((time()-log_0),1)
                times.append(str(time_log))
                temp_sps.append(str(temp_set_read))
                temp_ms.append(str(temp_meas))
                speed_sps.append(str(agit_set_read))
                speed_ms.append(str(agit_meas_read))
                heat_pows.append(str(heat_per))
                stirr_stats.append(str(stirr_is_on))
                err_stats.append(str(error_str))
                proc_stats.append(str(proc_status))
        
                sg.popup("Motor Current Error, Please Reset RS9000")
                
                Save_Logs(log_dict,log_headings,times,temp_sps,temp_ms,speed_sps,speed_ms,\
                              heat_pows,stirr_stats,err_stats,proc_stats)
                    
            break
        
        if (event == '-STOP3-'):
            proc_status = "Abort"
            window_3['-OUTPUT3_10-'].update(proc_status)
            heat_on = False
            stirr_on = False
            Set_On_Off(stirr_on, heat_on, sound_sh_on, sound_m_on, sound_l_on, devaddr, ram_HS_OnOff, max_wait)
            print("Aborting Process...")
    
            if (logs_on == True):
                
                Save_Logs(log_dict,log_headings,times,temp_sps,temp_ms,speed_sps,speed_ms,\
                              heat_pows,stirr_stats,err_stats,proc_stats)
                
            break
    
    
        if (event == '-QUIT3-' or event == sg.WIN_CLOSED):
    
            if (logs_on == True):
                
                Save_Logs(log_dict,log_headings,times,temp_sps,temp_ms,speed_sps,speed_ms,\
                              heat_pows,stirr_stats,err_stats,proc_stats)

            
            break
    
    window_3.close()
    
#------------------------------------------------------------------------------


            
#----------------------Check Microcontroller is Connected-----------------------

try:
    print('Trying to connect to server...')
    r1 = requests.get('http://'+IP_addr)
    print('Response of http://'+IP_addr+': ')
    print(r1.status_code)

except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
    print ("No server found, timed out. Check microcontroller is switched on and connected.")
else:
    print ("Microcontroller is working, ready to receive parameters.")


#-------------------------Main Loop------------------

Menu_Dialog()



    
