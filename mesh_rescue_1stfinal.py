import socket
import select
import json
import threading
import time
import sys
import copy
import os
import re

###
import difflib
import smbus2                 #import SMBus module of I2C
import serial
import datetime
import pynmea2
import bme280
###

sat_num = 1

#some MPU6050 Registers and their Address
PWR_MGMT_1   = 0x6B
SMPLRT_DIV   = 0x19
CONFIG       = 0x1A
GYRO_CONFIG  = 0x1B
INT_ENABLE   = 0x38
ACCEL_XOUT_H = 0x3B
ACCEL_YOUT_H = 0x3D
ACCEL_ZOUT_H = 0x3F
GYRO_XOUT_H  = 0x43
GYRO_YOUT_H  = 0x45
GYRO_ZOUT_H  = 0x47

SAMPLE_GPS_DATA = [
    [ 36.010278, 129.321111, 1000.0 ], #CanSat01(LGBldg): 36°00'37"N 129°19'16"E
    [ 36.011389, 129.311111, 1000.0 ], #CanSat02(Jamyung): 36°00'41"N 129°18'40"E
    [ 36.004722, 129.314167, 1000.0 ], #CanSat03(Yugang): 36°00'17"N 129°18'51"E
    [ 36.006667, 129.303333, 1000.0 ]  #CanSat04(JeMt): 36°00'24"N 129°18'12"E 
]

MAC_PTN = '[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}:[0-9a-f]{2}'
IPv4_PTN = '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+'

WLAN_MAC_LIST = [
  '0c:88:2b:00:8c:e4', '0c:88:2b:00:8c:df', '0c:88:2b:00:8c:cd', '3c:9b:d6:ec:46:15',
  '0c:88:2b:00:8c:cf', '0c:88:2b:00:8c:d5', '0c:88:2b:00:Bc:f2', 'Oc:88:2b:00:8c:e3'
]
BAT0_IP_LIST = [
  '192.168.199.1', '192.168.199.2', '192.168.199.3', '192.168.199.4'
]

lock = threading.Lock()

checksim = 1
sim_gps_data = copy.deepcopy(SAMPLE_GPS_DATA[sat_num-1])

neighbor_list = [] #[0]: wlan1_MAC, [1]: last seen time, [2]: list of bat0_MAC connected, [2][N][2]: list of bat0_IP
apclient_list = [] #[0]: MAC, [1]: ip
neighbor_list_temp = [] #[0]: wlan1_MAC, [1]: last seen time, [2]: list of bat0_MAC connected, [2][N][2]: list of bat0_IP
apclient_list_temp = []

#HOST = '127.0.0.1'
BASEHOST = '192.168.1.2'  #'192.168.1.53'
BASEPORT = 2500
BASEADDR = (BASEHOST, BASEPORT)
APNETWORK = '192.168.'+str(sat_num)
HOST = APNETWORK + '.1'
PORT = 10000
BUFSIZE = 1024
ADDR = (HOST, PORT)

checkbaseconn = 0
clientSocket_list = []
onlyclientSocket_list = []
clithr_event_list = []

default_msg_obj = {          #also same with meshinfo_msg packet
    "msg": {
        "sender": "CanSat0"+str(sat_num),
        "receiver": None,
        "time": None
    }
}
sensor_info_obj = {
        "req": False,
        "gps": { "lat": None, "lon": None, "alt":  None },
        "imu": { "acc": None, "gyr": None },
        "bme": { "temp": None, "pres": None, "humi": None }
}
nodeX_info_obj = {          #also same with meshinfo_msg packet
  "MAC": None,  
  "time": None,
}
refugX_info_obj = {          #also same with meshinfo_msg packet
  "ip": None,  
  "MAC": None,
}
help_info_obj = {
    "type": None,
    "text": None,    
    "refugee": None    
}

def initIMU(devaddr):
    bus.write_byte_data(devaddr, SMPLRT_DIV, 7)     #Write to sample rate reg
    bus.write_byte_data(devaddr, PWR_MGMT_1, 1)     #Write to power management register
    bus.write_byte_data(devaddr, CONFIG, 0)         #Write to Configuration register
    bus.write_byte_data(devaddr, GYRO_CONFIG, 24)   #Write to Gyro configuration register
    bus.write_byte_data(devaddr, INT_ENABLE, 1)     #Write to interrupt enable register

def read_IMU_data(devaddr, addr):
    #Accelero and Gyro value are 16-bit
    high = bus.read_byte_data(devaddr, addr)
    low = bus.read_byte_data(devaddr, addr+1)
    
    #concatenate higher and lower value
    value = ((high << 8) | low)
        
    #to get signed value from mpu6050
    if(value > 32768):
        value = value - 65536
    return value

def parseIMU(devaddr):
    #Read Accelerometer raw value
    acc_x = read_IMU_data(devaddr, ACCEL_XOUT_H)
    acc_y = read_IMU_data(devaddr, ACCEL_YOUT_H)
    acc_z = read_IMU_data(devaddr, ACCEL_ZOUT_H)
    
    #Read Gyroscope raw value
    gyro_x = read_IMU_data(devaddr, GYRO_XOUT_H)
    gyro_y = read_IMU_data(devaddr, GYRO_YOUT_H)
    gyro_z = read_IMU_data(devaddr, GYRO_ZOUT_H)
    
    #Full scale range +/- 250 degree/C as per sensitivity scale factor
    Ax = acc_x/16384.0
    Ay = acc_y/16384.0
    Az = acc_z/16384.0
    Acc_data = [Ax, Ay, Az]

    Gx = gyro_x/131.0
    Gy = gyro_y/131.0
    Gz = gyro_z/131.0
    Gyr_data = [Gx, Gy, Gz]
    
    #gyro_info = "Gx = {0:.2f} deg/s\tGy = {1:.2f} deg/s\t\tGz = {2:.2f} deg/s\r\nAx = {3:.2f} g\t\tAy = {4:.2f} g\t\tAz = {5:.2f} g\r\n".format(Gx, Gy, Gz, Ax, Ay, Az)
    return (Acc_data, Gyr_data)

def parseGPS(device):
    gps_msg = None
    for i in range(8):
        data = device.readline().decode()
        if data.find('GGA') > 0:
            gps_msg = pynmea2.parse(data)
            #print("Timestamp: %s -- Lat: %s %s -- Lon: %s %s -- Altitude: %s %s\n" 
            #        % (gps_msg.timestamp, gps_msg.lat, gps_msg.lat_dir, gps_msg.lon, gps_msg.lon_dir, gps_msg.altitude, gps_msg.altitude_units))
    if checksim == 0:
        return (gps_msg.lat, gps_msg.lon, gps_msg.altitude)
    else:
        return (sim_gps_data[0], sim_gps_data[1], sim_gps_data[2])

def parseBME(bus, address, calibration_params):
    # the sample method will take a single reading and return a
    # compensated_reading object
    data = bme280.sample(bus, address, calibration_params)

    # the compensated_reading class has the following attributes
    #print(data.id)
    #print(data.timestamp)
    #print("Temperature: %.2f -- Pressure: %.2f -- Humidity: %.2f\n" % (data.temperature, data.pressure, data.humidity))
    return (data.temperature, data.pressure, data.humidity)

def findNBCLhosts():
  #0. Initialization
  neighbor_list_temp = []
  apclient_list_temp = []
  #1. MAC address of wlan1 itself nodes(0 hop): wlan1 MAC
  ifconfig_str = os.popen('ifconfig')
  print(ifconfig_str)
  while True:
    sl = ifconfig_str.readline()  
    checkselfwlan = re.match('wlan1', sl.strip())
    if checkselfwlan: 
        break
    if sl == '' :
        print("no wlan1 active on Cansat0"+str(sat_num))
        return
  while True:
    sl = ifconfig_str.readline()       
    self_wlan_MAC = re.findall(MAC_PTN, sl.strip())
    if len(self_wlan_MAC) != 0: 
        neighbor_list_temp.append([self_wlan_MAC[0], float(0.000)])
        break
    if sl == '' :
        print("wlan1 MAC extraction error on Cansat0"+str(sat_num))
        return
  
  #2. list of wlan1's neighbor mesh nodes(1 hop): wlan1 MAC
  bctln_str = os.popen('sudo batctl n')  
  print(bctln_str)
  while True:
    sl = bctln_str.readline()  
    if sl == '' : break
    checkwlan = re.match('wlan1', sl.strip())
    if checkwlan:
      n_wlan_MAC = re.findall(MAC_PTN, sl.strip())
      n_wlan_times = re.findall('[0-9]+\.[0-9]+s', sl.strip())
      n_wlan_time = re.findall('[0-9]+\.[0-9]+', sl.strip())
      neighbor_list_temp.append([n_wlan_MAC[0], float(n_wlan_time[0])])

  #3. list of ip address linked(ARP) with MAC: bat0 MAC -> bat0 ip, wlan MAC -> wlan ip 
  arpn_str = os.popen('arp -n')
  while True:
    sl = arpn_str.readline()
    if sl == '' : break
    #find client MAC&ip
    if sl.strip().find('wlan2') != -1:
      client_MAC = re.findall(MAC_PTN, sl.strip())
      client_IP = re.findall(IPv4_PTN, sl.strip())
      if len(client_MAC) == 0 or len(client_IP) == 0:
        print("MAC or IP of AP client is incomplete")
      else:
        apclient_list_temp.append([client_MAC[0], client_IP[0]])
    #find neighbor node bat0 ip
  '''  
  print("List of Mesh Self&Neighbor CanSat Nodes:")
  for neighbor in neighbor_list_temp:
    print("[", neighbor[0], ", ", neighbor[1], "]")
    #for n_bat_MAC in neighbor[2]: print(n_bat_MAC)
  
  print("List of AP Client Refugees:")
  for client in apclient_list_temp:
    print(client)
  '''
  return (neighbor_list_temp, apclient_list_temp)

def socket_send_json(clientSocket, obj):
    for key in obj.keys():
        if key == "sensor" or key == "neighbor" or key == "client": break
        print(key, ":", obj[key])
    for key in obj.keys():
        if key == "msg" :  receiver = obj[key]["receiver"]
        else            :  infotype = key
#print(clientSocket)
    peeraddr = clientSocket.getpeername()
    data = json.dumps(obj)
    l = len(data)
    if "sensor" not in obj and "neighbor" not in obj and "client" not in obj:
        print(infotype + " obj data of length " + str(l) + " to be sent to " + receiver + ' at ' + str(peeraddr))
    try: 
        sendreturn = clientSocket.send(l.to_bytes(2, byteorder='big') + data.encode())
        #print(sendreturn)
        if "sensor" not in obj and "neighbor" not in obj and "client" not in obj:
            print("Data sent to " + receiver + ' successfully at ' + str(peeraddr))
    except:
        print("Failure to send data to " + receiver + ' at ' + str(peeraddr))

def meshinfo_thread():
    count = 0
    global neighbor_list
    global apclient_list
    global meshinfo_active
    global checkbaseconn
    #checkbaseconn flag check required
    try:
        while True:
            lock.acquire()
            meshinfo_active = 1
            lock.release()
            msg_obj = copy.deepcopy(default_msg_obj)
            if base_addr[0] == BASEADDR[0] : 
                msg_obj["msg"]["receiver"] = 'Base'
            else : 
                print('Base address error; %s:%s'%base_addr)
                return
            sendtime = datetime.datetime.now()
            msg_obj["msg"]["time"] = sendtime.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            
            obj_sensor = copy.deepcopy(msg_obj)
            #1. Sensor Info
            obj_sensor["sensor"] = copy.deepcopy(sensor_info_obj)
            lat, lon, alt = parseGPS(uart)
            acc, gyr = parseIMU(MPU_Address)
            temp, pres, humi = parseBME(bus, BME_Address, bme_calibration_params)
            obj_sensor["sensor"]["gps"] = { "lat": lat, "lon": lon, "alt": alt }
            obj_sensor["sensor"]["imu"] = { "acc": acc, "gyr": gyr } # add "mag": [0.0, 0.0, 0.0]
            obj_sensor["sensor"]["bme"] = { "temp": temp, "pres": pres, "humi": humi }
            
            socket_send_json(baseclientSocket, obj_sensor)         
            
            lock.acquire()
            neighbor_list, apclient_list = findNBCLhosts()
            #2. Neighbor Info
            lock.release()
            obj_neighbor = copy.deepcopy(msg_obj)
            obj_neighbor["neighbor"] = {}
            node_num = 0
            for neighbor in neighbor_list:
                lastseen = sendtime - datetime.timedelta(milliseconds=neighbor[1]*1000)
                nodeX_key = "node"+str(node_num)
                obj_neighbor["neighbor"][nodeX_key] = copy.deepcopy(nodeX_info_obj)
                obj_neighbor["neighbor"][nodeX_key]["MAC"] = neighbor[0]
                obj_neighbor["neighbor"][nodeX_key]["time"] = lastseen.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                node_num = node_num + 1

            socket_send_json(baseclientSocket, obj_neighbor)      
                
            #3. Client Info
            obj_client = copy.deepcopy(msg_obj)
            obj_client["client"] = {}
            refug_num = 0
            for client in apclient_list:
                refug_num = refug_num + 1
                refugX_key = "refug"+str(refug_num)
                obj_client["client"][refugX_key] = copy.deepcopy(refugX_info_obj)
                obj_client["client"][refugX_key]["MAC"] = client[0]
                obj_client["client"][refugX_key]["ip"] = client[1]
                
            socket_send_json(baseclientSocket, obj_client)
            
            count += 1
            time.sleep(3)
            sim_gps_data[0] = sim_gps_data[0] + 0.0001
            sim_gps_data[1] = sim_gps_data[1] - 0.0001
    except:
        print('meshinfo_thread Exception; %s:%s'%base_addr)
        lock.acquire()
        meshinfo_active = 0
        checkbaseconn = 0
        lock.release()
        return    
                    
def sensor_thread(clientSocket):
    count = 0
    sensorrefug_ip = clientSocket.getpeername()[0]
    apclient_list_cur = copy.deepcopy(apclient_list)
    try:
        obj_sensor = copy.deepcopy(default_msg_obj)
        #if client_addr[0].find(APNETWORK) != -1 :
        ip_num = sensorrefug_ip.split(".")
        obj_sensor["msg"]["receiver"] = 'Mobile' + ip_num[2] + '_' + ip_num[3]
        obj_sensor["msg"]["time"] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        obj_sensor["sensor"] = copy.deepcopy(sensor_info_obj)
        print("sensor thread start", obj_sensor)
    except Exception as e:
        print('Exception at sensor_thread; refugee %s:%s ' %clientSocket.getpeername())
        return
    
    while True:
        for clithr_event in clithr_event_list:
            if clithr_event["client"] == clientSocket:
                event_sensor = clithr_event["sensor_event"]
        print("==================event sensor: ", event_sensor.is_set())
        if event_sensor.is_set():
            break
        #if gpio_ConnErr == 1:
        #    break
        lat, lon, alt = parseGPS(uart)
        acc, gyr = parseIMU(MPU_Address)
        temp, pres, humi = parseBME(bus, BME_Address, bme_calibration_params)
        
        obj_sensor["sensor"]["gps"] = { "lat": lat, "lon": lon, "alt": alt }
        obj_sensor["sensor"]["imu"] = { "acc": acc, "gyr": gyr } # add "mag": [0.0, 0.0, 0.0]
        obj_sensor["sensor"]["bme"] = { "temp": temp, "pres": pres, "humi": humi }
    
        socket_send_json(clientSocket, obj_sensor)
        count += 1
        time.sleep(1)

def help_thread(obj_help_recv, clientSocket):
    count = 0
    global checkbaseconn
    global apclient_list
    apclient_list_config = copy.deepcopy(apclient_list)
    helprefug_ip = clientSocket.getpeername()[0]
    try:
        obj_help_send = copy.deepcopy(default_msg_obj)
        obj_dispatch_send = copy.deepcopy(default_msg_obj)

        ip_num = helprefug_ip.split(".")
        obj_help_send["msg"]["receiver"] = 'Base'
        obj_dispatch_send["msg"]["receiver"] = 'Mobile' + ip_num[2] + '_' + ip_num[3]
        obj_help_send["msg"]["time"] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        print("msg setting : ", obj_help_send)
        print("help thread start")        
    except Exception as e:
        print('Exception at help_thread; refugee %s:%s / base %s:%s ' %clientSocket.getpeername() %BASEADDR)
        return    
    try:
        print("help message from mobile: ", str(obj_help_recv))
        '''for clithr_event in clithr_event_list:
            #print(clithr_event)
            if clithr_event["client"] == clientSocket:
                event_help = clithr_event["help_event"]
        if event_help.is_set():
            print
            return
        '''
        obj_help_send['help'] = copy.deepcopy(obj_help_recv['help'])
        print("help_send: ", obj_help_send, "help_recv: ", obj_help_recv)
        if ('type' in obj_help_recv['help']) and (obj_help_recv['help']['type'] == 'help') :
            #append GPS of refugee
            if obj_help_recv['help']['refugee']['gps']['lat'] != "" and obj_help_recv['help']['refugee']['gps']['lon'] != "":   
                print("GPS data of refugee exists in help msg from refugee")
            else :   
                print("NO gps data from mobile: sending CanSat's GPS")            
                lat, lon, alt = parseGPS(uart)
                obj_help_send['help']['refugee']['gps'] = { "lat": lat, "lon": lon}
            #append MAC of refugee  
            for refugee in apclient_list_config:
                if refugee[1] == helprefug_ip:
                    print("found the same IP")
                    obj_help_send['help']['refugee']['MAC'] = refugee[0]
            if not ('MAC' in obj_help_send['help']['refugee']):
                print("No refugee IP matched")
        else : 
            print("Help msg type not help")
            return
        
        print("current base connection: ", checkbaseconn)
        if not checkbaseconn:
            obj_help_send['msg']['receiver'] = obj_dispatch_send["msg"]["receiver"]
            obj_help_send['help']['text'] = "Connection with the base station is lost: Please wait a while and try again."
            print(obj_help_send)
            #socket_send_json(clientSocket, obj_help_recv)
            return
        
        socket_send_json(baseclientSocket, obj_help_send)
        
        data_dispatch = baseclientSocket.recv(BUFSIZE)
        print("dispatch message from base: ", str(data_dispatch))
        obj_dispatch_recv = json.loads(data_dispatch[2:])

    except Exception as e:
        print('Exception at help_thread; refugee %s:%s / base %s:%s ' %clientSocket.getpeername() %BASEADDR)
        return    
                              
def baserecv_thread():
    count = 0
    global baserecv_active
    global onlyclientSocket_list
    global apclient_list
    global checkbaseconn
    try:
        obj_help_send = copy.deepcopy(default_msg_obj)
        if baseclientSocket.getpeername()[0] != BASEADDR[0]: Exception    
    except Exception as e:
        print('Exception at baserecv_thread; base %s:%s ' %BASEADDR)
        lock.acquire()
        baserecv_active = 0
        lock.release()
        return
    
    try:
        while True:
            time.sleep(1)
            lock.acquire()
            baserecv_active = 1
            lock.release()
            

            baserecv_data = baseclientSocket.recv(BUFSIZE)
            print("+++++++++++++++++++++base message received!+++++++++++++++++++++")
            length = int.from_bytes(baserecv_data[:2], 'big')
            #print(str(cur_clientSocket))
            print("from base: " + str(baserecv_data[2:]) + ' len='+str(length))
            # Check packet message syntax
            if baserecv_data[2] != 123: # b'{':
                print("Improper json syntax from base")
                continue
            obj_base_recv = json.loads(baserecv_data[2:])
            print("received data=" + str(obj_base_recv) + "length=%d" % len(str(obj_base_recv)))
        
            if obj_base_recv['msg']['sender'] != 'Base' or obj_base_recv['msg']['receiver'] != obj_help_send["msg"]["sender"] :
                print("Improper msg syntax from base")
                continue
            elif 'help' not in obj_base_recv or 'type' not in obj_base_recv['help']:
                print("Not a help message from base")
                continue
            
            obj_help_send['help'] = obj_base_recv['help']
            if obj_base_recv['help']['type'] == 'auto':
                if onlyclientSocket_list:
                    print("clientSocket list not empty")
                    for clientSocket in onlyclientSocket_list:
                        print(clientSocket)
                        ip_num = clientSocket.getpeername()[0].split(".")
                        obj_help_send["msg"]["receiver"] = 'Mobile' + ip_num[2] + '_' + ip_num[3]
                        obj_help_send["msg"]["time"] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                        socket_send_json(clientSocket, obj_help_send)
                else:
                    print("No refugee client in list")
                    continue
                
            elif obj_base_recv['help']['type'] == 'dispatch':
                for clientSocket in onlyclientSocket_list:
                    for apclient in apclient_list:
                        if obj_base_recv['help']['refugee']['MAC'] == apclient[0] and clientSocket.getpeername()[0] == apclient[1] :
                            ip_num = clientSocket.getpeername()[0].split(".")
                            #re.split(".", clientSocket.getpeername()[0])
                            obj_help_send["msg"]["receiver"] = 'Mobile' + ip_num[2] + '_' + ip_num[3]
                            obj_help_send["msg"]["time"] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                            socket_send_json(clientSocket, obj_help_send)
                            print("send done at baserecv thread")
                print("checkpoint at baserecv")
                print(obj_help_send['msg']['receiver'])
                if obj_help_send['msg']['receiver'] == "None":
                    print("Refugee waiting for dispatch is lost")        
            else:
                print("Not a help message from base")
                continue
    except Exception as e:
        print('Exception at baserecv_thread; base %s:%s ' %BASEADDR)
        lock.acquire()
        baserecv_active = 0
        lock.release()
        return


if __name__ == '__main__':
    #Serial Connection Initialization
    #gpio_ConnErr = 0
    try:
        bus = smbus2.SMBus(1)     # or bus = smbus.SMBus(0) for older version boards
        MPU_Address = 0x68      # MPU9250 device address
        BME_Address = 0x76      # BME280 device address

        initIMU(MPU_Address)
        uart = serial.Serial(                \
            port='/dev/ttyS0',                \
            baudrate = 9600,                \
            parity=serial.PARITY_NONE,        \
            stopbits=serial.STOPBITS_ONE,    \
            bytesize=serial.EIGHTBITS,        \
            timeout=1                        \
        )
        bme_calibration_params = bme280.load_calibration_params(bus, BME_Address)
        print('uart, i2c connection all clear')

        counter=0
    except:
        gpio_ConnErr = 1
        print("GPIO connecting error!\n")


    baseclientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    baseclientSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serverSocket.bind(ADDR)
    serverSocket.listen(100)
    clientSocket_list.append(serverSocket)  #list of client sockets to be saved
    meshinfo_active = 0
    baserecv_active = 0

    #Test: use gethost, remotenetwork 
    host_name = socket.gethostname()
    host_addr = socket.gethostbyname(host_name)
    print('Host Name: ' + str(host_name) + '   Host IP: ' + str(host_addr))
    print('Base Station: ' + str(baseclientSocket))
    threading.Event()
    # Loop of receiving socket from clients and opening threads to send back
    loopcount = 0
    whilecount = 0
    while True:
        if not checkbaseconn:
            try:
                print(baseclientSocket)
                baseclientSocket.connect(BASEADDR)
                print(baseclientSocket)
                base_addr = baseclientSocket.getpeername()
                print("connected base ip address :", base_addr)
                checkbaseconn = 1
            except Exception as e:
                print('Exception of base connection; %s:%s'%BASEADDR)
                checkbaseconn = 0
        
        if checkbaseconn and not meshinfo_active: 
            thread_meshinfo = threading.Thread(target=meshinfo_thread, args=())
            thread_meshinfo.start()
        if checkbaseconn and not baserecv_active: 
            print("initial checkbaseconn: ", checkbaseconn)
            thread_autohelp = threading.Thread(target=baserecv_thread,  args=())
            thread_autohelp.start()
        
        if whilecount % 10 == 0: 
            print("=================Current Threads Activated====================")
            print("checkbaseconn: ", checkbaseconn,  "meshinfo_active: ", meshinfo_active, "autohelp_active: ", baserecv_active)
            print("whilecount: ", whilecount)
            for threadi in threading.enumerate():   print(threadi.name)
            print("==============================================================")

        input_ready, _, _ = select.select(clientSocket_list, [], [], 1)

    
        # Include new mobile refugee client socket in list 
        for cur_clientSocket in input_ready:
            if cur_clientSocket == serverSocket:        #for hosts newly connecting to server
                newclientSocket, addr_info = serverSocket.accept()
                print('connected to ' + str(newclientSocket))
                print('peer host address:' + str(newclientSocket.getpeername()))
                clientSocket_list.append(newclientSocket)
                onlyclientSocket_list.append(newclientSocket)
                print('number of clients in list: %d' % len(clientSocket_list))
                print(*clientSocket_list, sep = "\n\n")
                clithr_event_elm = {"client"    : newclientSocket,
                                    "sensor_event"  : threading.Event(),
                                    "help_event"    : threading.Event()
                                    }
                clithr_event_list.append(clithr_event_elm)
                print(*clithr_event_list, sep = "\n\n")
                loopcount = loopcount + 1
                print("adding client done: loop count =", loopcount)
            # receive packet(=2byte_len + msg payload) from mobile.
            else: 
                cur_data = cur_clientSocket.recv(BUFSIZE)
                length = int.from_bytes(cur_data[:2], 'big')
                #print(str(cur_clientSocket))
                print("from mobile: " + str(cur_data[2:]) + ' len='+str(length))
                # Chcck packet message syntax
                if cur_data[2] == 123: # b'{':
                    obj_cli_recv = json.loads(cur_data[2:])
                    print("received data=" + str(obj_cli_recv) + "length=%d" % len(str(obj_cli_recv)))
                    
                    # 'Sensor' Button Pressed
                    if ("sensor" in obj_cli_recv) and ("req" in obj_cli_recv["sensor"]):                  
                        #event_sensor = threading.Event()
                        if obj_cli_recv["sensor"]["req"] == True:
                            for clithr_event in clithr_event_list:
                                if clithr_event["client"] == cur_clientSocket:
                                    clithr_event["sensor_event"].clear()
                                    #print("sensor event of " + str(clithr_event["client"]) + " : " + str(clithr_event["sensor_event"].is_set()))
                            thread_sensor = threading.Thread(target=sensor_thread, args=(cur_clientSocket,))
                            thread_sensor.start()
                        else:
                            for clithr_event in clithr_event_list:
                                if clithr_event["client"] == cur_clientSocket:
                                    clithr_event["sensor_event"].set()
                            thread_sensor.join()
                            
                    # 'Help' Button Pressed
                    elif ("help" in obj_cli_recv) and ("type" in obj_cli_recv["help"]) and obj_cli_recv["help"]["type"] == "help":
                        #send the received msg to base station
                        thread_help = threading.Thread(target=help_thread, args=(obj_cli_recv,cur_clientSocket))
                        thread_help.start()
                    else:
                        print("No request offered that can be done by CanSat")

                else:
                    cur_data = input(' -> ')
                    l = len(cur_data)
                    # send 2byte_len + payload to mobile
                    cur_clientSocket.send(l.to_bytes(2, byteorder='big') + cur_data.encode())
                
                loopcount = loopcount + 1
                print("adding client done: loop count =", loopcount)
                # receive packet(=2byte_len + msg payload) from mobile.
        whilecount = whilecount + 1
    baseclientSocket.close()
    for clientSocket in clientSocket_list:
        clientSocket.close()
