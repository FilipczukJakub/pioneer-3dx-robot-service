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

main_server_running = False
stop = False
msg = Twist()
controlled_move_thread = None
avoid_obstacle_thread = None

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
    global stop
    global msg
    global controlled_move_thread
    global avoid_obstacle_thread
    try:
        async for message in websocket:
            print(message)
            if(not message.startswith("message:")):
                jsonString = json.loads(message)
                msg = toTwist(jsonString)
            else:
                avoid_obstacle_thread.start()
    except Exception as e:
        print('blad servera ' + e)

def pose_callback(pose):
    sonars = PointCloud()
    while True:
        sonars = pose
        print(sonars)
        time.sleep(5)

def obstacle_avoidance():
    print('subscribed to sonars')
    sub = rospy.Subscriber("/RosAria/sonar",PointCloud,callback=pose_callback)

async def main_server(ip):
    global stop
    async with websockets.serve(echo,ip,8765):
        print("server is listening on " + ip + ":8765")
        await stop

def controlled_move():
    global msg
    pub = rospy.Publisher("/RosAria/cmd_vel", Twist, queue_size=10)
    print('move service started')
    while True:
        # print('move vector: ' + str(msg))        
        pub.publish(msg)
        time.sleep(0.1)

def broadcast_server(ip):
    global msg
    s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(('0.0.0.0',12345))
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    print('broadcast started')
    while(True):
        data,adres= s.recvfrom(1024)
        message = data.decode('ascii')
        if(message == 'ip_request'):
            print('received broadcast request for my ip ' + data.decode('ascii') + ip)
            s.sendto(ip.encode('ascii'),(adres[0],adres[1]))
        elif(message == 'stop'):
            print('emergancy stop')
            msg = toTwist(0)

async def start_controlling_service():
    global stop
    global controlled_move_thread
    global avoid_obstacle_thread
    ip = (([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")] or [[(s.connect(("8.8.8.8", 53)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) + ["no IP found"])[0]    
    broadcast_thread = threading.Thread(target=broadcast_server,args=(ip,))  
    controlled_move_thread = threading.Thread(target=controlled_move,args=())
    avoid_obstacle_thread = threading.Thread(target=obstacle_avoidance,args=())
    broadcast_thread.start()
    controlled_move_thread.start()
    loop = asyncio.get_event_loop()
    stop = loop.create_future()
    loop.add_signal_handler(signal.SIGTERM, stop.set_result, None)
    await main_server(ip)

if __name__ == '__main__':
    rospy.init_node('remote_listener')
    asyncio.run(start_controlling_service())
    rospy.spin()
