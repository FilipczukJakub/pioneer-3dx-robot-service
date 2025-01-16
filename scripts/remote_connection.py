#!/usr/bin/env python3
import rospy
from geometry_msgs.msg import Twist
from std_msgs.msg import Int8
from sensor_msgs.msg import PointCloud
from websockets.server import serve
import websockets
import asyncio
import socket
import signal
import threading
import json
import time
import os

global_stop = False
vel = Twist()
gripper_command = Int8(data=2)
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

async def message_Handler(websocket):
    global vel
    global ping_thread
    global gripper_command
    ping_thread = threading.Thread(target=ping_handler,args=(websocket,))
    ping_thread.start()
    while True:
        message = await websocket.recv()
        print(message)
        split_message = message.split('###')
        if len(split_message) == 2 :
            message_type = split_message[0]
            jsonString = json.loads(split_message[1])
            if 'gripper' == message_type:
                print(jsonString)
                gripper_command.data = int(jsonString)
            elif 'move' == message_type:
                vel = toTwist(jsonString)

async def main_server(ip,stop):
    async with websockets.serve(message_Handler,'0.0.0.0',8765):
        print("server is listening on " + str(ip) + ":8765")
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
    global vel
    global global_stop
    pub = rospy.Publisher("/RosAria/cmd_vel", Twist, queue_size=10)
    print('move service started')
    while not global_stop:
        pub.publish(vel)
        time.sleep(0.1)

def controlled_gripper():
    global gripper_command
    global global_stop
    pub = rospy.Publisher("/RosAria/gripper", Int8, queue_size=10)
    print('gripper service started')
    while not global_stop:
        pub.publish(gripper_command)
        time.sleep(0.1)

def broadcast_server(ip):
    global vel
    global global_stop
    s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(('0.0.0.0',12345))
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    print('broadcast started')
    while not global_stop:
        data,adres= s.recvfrom(1024)
        message = data.decode('ascii')
        if(message == 'ip_request'):
            print('received broadcast request for my ip ' + data.decode('ascii') + str(ip))
            s.sendto(ip.encode('ascii'),(adres[0],adres[1]))
        elif(message == 'stop'):
            print('emergancy stop')
            vel = toTwist(0)

async def start_controlling_service():
    global global_stop
#    ip = (([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")] or [[(s.connect(("8.8.8.8", 53)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) + ["no IP found"])[0]    
#    ip = socket.gethostbyname("host.docker.internal")
    ip = os.getenv("HOST_IP")

    broadcast_thread = threading.Thread(target=broadcast_server,args=(ip,))  
    controlled_move_thread = threading.Thread(target=controlled_move,args=())
    gripper_move_thread = threading.Thread(target=controlled_gripper,args=())

    broadcast_thread.start()
    controlled_move_thread.start()
    gripper_move_thread.start()
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

