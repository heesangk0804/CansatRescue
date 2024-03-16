import socket
import select
import json
import threading
import time
import sys

#HOST = '127.0.0.1'
BASEHOST = '192.168.2.19'  #'192.168.0.1'
BASEPORT = 2500
BASEADDR = (BASEHOST, BASEPORT)
HOST = '192.168.1.1'
PORT = 10000
BUFSIZE = 1024
ADDR = (HOST, PORT)

baseclientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

baseclientSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

serverSocket.bind(ADDR)

serverSocket.listen(100)

#input_list = [serverSocket]

sensor_message = {
    "msg": {
        "sender": "rpi1",
        "receiver": "mobile",
        "gps": [35.0, 129.0]
    }
}

#Test: use gethost, remotenetwork 
host_name = socket.gethostname()
host_ip = socket.gethostbyname(host_name)
#base_name = 'raspberrypi2'
#base_ip = socket.gethostbyname(base_name)
print('Host Name: ' + str(host_name) + '   Host IP: ' + str(host_ip))
#       + '   Base Name: ' + str(base_name) + '   Base IP: ' + str(base_ip) )

def sensor_thread(event):
    count = 0
    obj = sensor_message
    #print("sensor thread start")
    while True:
        if event.is_set():
            break
        obj["msg"]["gps"][0] = 35.0 + 0.1 * (count % 10)
        obj["msg"]["gps"][1] = 129.0 + 0.1 * (count % 10)
        data = json.dumps(obj)
        l = len(data)
        print('data:' + str(data) + 'length:' + str(l))
        # send 2byte_len + payload to mobile
        clientSocket.send(l.to_bytes(2, byteorder='big') + data.encode())
        print('send successful')
        count += 1
        time.sleep(1)
    return

"""



while True:

    input_ready, _, _ = select.select(input_list, [], [])

    for socket in input_ready:
        if socket == serverSocket:
            clientSocket, addr_info = serverSocket.accept()
            print(clientSocket)
            input_list.append(clientSocket)

        else:
            data = socket.recv(BUFSIZE)
            if data == b'GET':
                socket.send(data)
            else:
                socket.close()
                input_list.remove(socket)

serverSocket.close()

"""
        
def help_thread(data_help):
    count = 0
    
    try:
        baseclientSocket.connect(BASEADDR)
        
        while True:
            baseclientSocket.send(data_help)
            data_resp = baseclientSocket.recv(BUFSIZE)
            print("from base: " + str(data_resp[2:]) + ' len=' + str(int.from_bytes(data_resp[:2], 'big')))

            if data_resp[2] == 123:
                jsonobj_resp = json.loads(data_resp[2:])
                msg_resp = jsonobj_resp["msg"]
                if msg_resp.get("dispatch") and msg_resp["dispatch"] == "true":
                    clientSocket.send(data_resp)
                    print('send successful')
                    count += 1
                    time.sleep(1)
                    break
                print("Done")
            print("Loop done")
                    
    except Exception as e:
        print('%s:%s'%BASEADDR)
        
        return



clientSocket, addr_info = serverSocket.accept()
print('connected to ' + str(clientSocket))

thread_sensor = 1
event_sensor = threading.Event()

while True:
        
    #clientSocket, addr_info = serverSocket.accept()
    '''
    input_ready, _, _ = select.select(input_list, [], [])

    for socket in input_ready:
        if socket == serverSocket:
            clientSocket, addr_info = serverSocket.accept()
            print('connected to ' + str(clientSocket))
            input_list.append(clientSocket)

        else:
            data = socket.recv(BUFSIZE)
            if data == b'GET':
                socket.send(data)
            else:
                socket.close()
                input_list.remove(socket)
    '''
    # receive data stream from mobile.
    # packet is composed of 2byte_len + payload

    data = clientSocket.recv(BUFSIZE)
    length = int.from_bytes(data[:2], 'big')
    print("from mobile: " + str(data[2:]) + ' len='+str(length))
    print('recv return datatype: ' + str(type(data)))
    for threadi in threading.enumerate():
            print(threadi.name)
    
    if data[2] == 123: # b'{':
        jsonobj = json.loads(data[2:])
        msg = jsonobj["msg"]
        print("data=" + str(msg) + "length=%d" % len(str(msg)))
        if msg.get("sensor"):
            #event_sensor = threading.Event()
            print("event sensor:%s" % str(event_sensor))
            if msg["sensor"] == "true":
                event_sensor.clear()
                thread_sensor = threading.Thread(target=sensor_thread, args=(event_sensor,))
                #thread_sensor.daemon = True
                thread_sensor.start()
            elif msg["sensor"] == "false":
                event_sensor.set()
                thread_sensor.join()
                
        #print("data['msg']['gps']=%s" % (str(jsonobj['msg']['gps'])))
        elif msg.get("help") and msg["help"] == "true":
            #send the received msg to base station
            thread_help = threading.Thread(target=help_thread, args=(data,))
            thread_help.start()
        #print("data['msg']['gps']=%s" % (str(jsonobj['msg']['gps'])))
        
    else:
        data = input(' -> ')
        l = len(data)
        # send 2byte_len + payload to mobile
        clientSocket.send(l.to_bytes(2, byteorder='big') + data.encode())

baseclientSocket.close()
clientSocket.close()
serverSocket.close()
