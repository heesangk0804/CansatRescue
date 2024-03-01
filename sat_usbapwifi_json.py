import sys
import time
import difflib
import smbus2
from time import sleep
import serial
import datetime
import pynmea2
import bme280
import socket
import json
import select

HOST = '192.168.0.82'
PORT = 10000
BUFSIZE = 1024
ADDR = (HOST, PORT)


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


def initIMU(devaddr):
    bus.write_byte_data(devaddr, SMPLRT_DIV, 7)
    bus.write_byte_data(devaddr, PWR_MGMT_1, 1)
    bus.write_byte_data(devaddr, CONFIG, 0)
    bus.write_byte_data(devaddr, GYRO_CONFIG, 24)
    bus.write_byte_data(devaddr, INT_ENABLE, 1)

def read_raw_data(devaddr, addr):
    high = bus.read_byte_data(devaddr, addr)
    low = bus.read_byte_data(devaddr, addr+1)
    value = ((high << 8) | low)
        
    if(value > 32768):
        value = value - 65536
    return value

def parseIMU(devaddr):
    acc_x = read_raw_data(devaddr, ACCEL_XOUT_H)
    acc_y = read_raw_data(devaddr, ACCEL_YOUT_H)
    acc_z = read_raw_data(devaddr, ACCEL_ZOUT_H)
    
    gyro_x = read_raw_data(devaddr, GYRO_XOUT_H)
    gyro_y = read_raw_data(devaddr, GYRO_YOUT_H)
    gyro_z = read_raw_data(devaddr, GYRO_ZOUT_H)
    
    Ax = acc_x/16384.0
    Ay = acc_y/16384.0
    Az = acc_z/16384.0
    Acc_data = [Ax, Ay, Az]

    Gx = gyro_x/131.0
    Gy = gyro_y/131.0
    Gz = gyro_z/131.0
    Gyr_data = [Gx, Gy, Gz]
    
    return (Acc_data, Gyr_data)

def parseGPS(device):
    msg = None
    for i in range(8):
        data = device.readline().decode()
        if data.find('GGA') > 0:
            msg = pynmea2.parse(data)
    if msg:
        return (msg.lat, msg.lon, msg.altitude)
    else:
        return (None, None, None)

def parseBME(bus, address, calibration_params):
    data = bme280.sample(bus, address, calibration_params)
    return (data.temperature, data.pressure, data.humidity)


if __name__ == '__main__':

    serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
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

        counter=0
        
        serverSocket.bind(ADDR)
        print('bind')
        serverSocket.listen(100)
        print('listen')
        clientSocket, addr_info = serverSocket.accept()
        print('accept')
        print(clientSocket)
        
        while True:
            sleep(1)

            lat, lon, alt = parseGPS(uart)
            
            acc, gyr = parseIMU(MPU_Address)

            temp, pres, humi = parseBME(bus, BME_Address, bme_calibration_params)

            satobj = {}
            satobj["msg"] = { 
                    "id": "001",
                    "sender": "sat01",
                    "receiver": "stn01",
                    "time": "20240218"
                }
            satobj["sensor"] = {} 
            satobj["sensor"]["gps"] = { "lat": lat, "lon": lon, "alt": alt }
            satobj["sensor"]["imu"] = { "acc": acc, "gyr": gyr } # add "mag": [0.0, 0.0, 0.0]
            satobj["sensor"]["bme"] = { "temp": temp, "pres": pres, "humi": humi }

            jsonstr = json.dumps(satobj)
            print(jsonstr)

            clientSocket.send(jsonstr.encode())

    
    except:
        print("GPIO connecting error!\n")
        print('%s:%s'%ADDR)
        sys.exit()

    clientSocket.close()
    print('close')

serverSocket.close()
print('close')
