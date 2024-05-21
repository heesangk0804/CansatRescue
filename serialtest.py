import serial
import time
import pynmea2

uartGPS = serial.Serial(                \
            port='/dev/ttyS0',                \
            baudrate = 9600,                \
            parity=serial.PARITY_NONE,        \
            stopbits=serial.STOPBITS_ONE,    \
            bytesize=serial.EIGHTBITS,        \
            timeout=1                        \
        )

while True:
   data = uartGPS.readline().decode()
   print(data)
   msg = pynmea2.parse(data)
   print(msg)
   time.sleep(0.01)
