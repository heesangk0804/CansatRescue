import socket
import select
import json
import threading
import time

#HOST = '127.0.0.1'
HOST = '192.168.0.78'
PORT = 10000
BUFSIZE = 1024
ADDR = (HOST, PORT)

serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

serverSocket.bind(ADDR)

serverSocket.listen(100)

clientSocket, addr_info = serverSocket.accept()
print('connected to ' + str(clientSocket))

sensor_message = {
    "msg": {
        "sender": "rpi1",
        "receiver": "mobile",
        "gps": [35.0, 129.0]
    }
}

def sensor_thread():
    count = 0
    obj = sensor_message
    #print("sensor thread start")
    while True:
        obj["msg"]["gps"][0] = 35.0 + 0.1 * (count % 10)
        obj["msg"]["gps"][1] = 129.0 + 0.1 * (count % 10)
        data = json.dumps(obj)
        l = len(data)
        # send 2byte_len + payload to mobile
        clientSocket.send(l.to_bytes(2, byteorder='big') + data.encode())
        count += 1
        time.sleep(1)

while True:
    # receive data stream from mobile.
    # packet is composed of 2byte_len + payload
    data = clientSocket.recv(BUFSIZE)
    length = int.from_bytes(data[:2], 'big')
    print("from mobile: " + str(data[2:]) + ' len='+str(length))
    if data[2] == 123: # b'{':
        jsonobj = json.loads(data[2:])
        msg = jsonobj["msg"]
        if msg.get("sensor") and msg["sensor"] == "true":
            thread = threading.Thread(target=sensor_thread, args=())
            thread.start()
        #print("data['msg']['gps']=%s" % (str(jsonobj['msg']['gps'])))
    else:
        data = input(' -> ')
        l = len(data)
        # send 2byte_len + payload to mobile
        clientSocket.send(l.to_bytes(2, byteorder='big') + data.encode())

clientSocket.close()
serverSocket.close()
