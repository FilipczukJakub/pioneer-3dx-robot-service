#!/usr/bin/env python3
import rospy
from geometry_msgs.msg import Twist
from sensor_msgs.msg import PointCloud
from websockets.server import serve
import websockets
import asyncio
import socket
import signal
import threading
import json
import time

global_stop = False
msg = Twist()
ping_thread = threading.Thread

def toTwist(jsonString):
    local_msg = Twist()
    if(jsonString != 0):
        local_msg.linear.x = jsonString["Linear"]["x"]
        local_msg.linear.y = jsonString["Linear"]["y"]
        local_msg.linear.z = jsonString["Linear"]["z"]
        local_msg.angular.x = jsonString["Angular"]["x"]
        local_msg.angular.y = jsonString["Angular"]["y"]
        local_msg.angular.z = jsonString["Angular"]["z"]
    return local_msg

async def echo(websocket):
    global msg
    global ping_thread
    ping_thread = threading.Thread(target=ping_handler,args=(websocket,))
    ping_thread.start()
    while True:
        message = await websocket.recv()
        print(message)
        jsonString = json.loads(message)
        msg = toTwist(jsonString)

async def main_server(ip,stop):
    async with websockets.serve(echo,'0.0.0.0',8765):
        print("server is listening on " + ip + ":8765")
        await stop
    print('server stopped')

def ping_handler(websocket):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(ping(websocket))
    loop.close()

async def ping(websocket):
    global global_stop
    while not global_stop:
        try:
            await websocket.send('ping')
            print('ping')
            time.sleep(2)
        except Exception as e:
            break

def controlled_move():
    global msg
    global global_stop
    pub = rospy.Publisher("/RosAria/cmd_vel", Twist, queue_size=10)
    print('move service started')
    while not global_stop:
        pub.publish(msg)
        time.sleep(0.1)

def broadcast_server(ip):
    global msg
    global global_stop
    s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(('0.0.0.0',12345))
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    print('broadcast started')
    while not global_stop:
        data,adres= s.recvfrom(1024)
        message = data.decode('ascii')
        if(message == 'ip_request'):
            print('received broadcast request for my ip ' + data.decode('ascii') + ip)
            s.sendto(ip.encode('ascii'),(adres[0],adres[1]))
        elif(message == 'stop'):
            print('emergancy stop')
            msg = toTwist(0)

async def start_controlling_service():
    global global_stop
#    ip = (([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")] or [[(s.connect(("8.8.8.8", 53)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) + ["no IP found"])[0]    
    ip = socket.gethostbyname("host.docker.internal")
    broadcast_thread = threading.Thread(target=broadcast_server,args=(ip,))  
    controlled_move_thread = threading.Thread(target=controlled_move,args=())
    broadcast_thread.start()
    controlled_move_thread.start()
    loop = asyncio.get_event_loop()
    stop = loop.create_future()
    loop.add_signal_handler(signal.SIGINT, stop.set_result, None)
    await main_server(ip,stop)
    global_stop = True
    print('finish threads')

if __name__ == '__main__':
    rospy.init_node('remote_listener')
    asyncio.run(start_controlling_service())
    rospy.spin()

