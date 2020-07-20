print("server has started")

import socket
import pickle
import sys
from threading import Thread, Lock, Condition
from time import sleep
# enable socket connections

SOCK_IP = '0.0.0.0'
SOCK_PORT = 9001

all_clients = []
mutex = Lock()
def client_handler(client_id):
    global serversocket
    clientsocket, address = client_id
    cl_name = (clientsocket.recv(1024).decode())
    print(f"new client connected {cl_name}")
    with mutex:
        all_clients.append((client_id, cl_name))

    while True:
        sleep(0.01)
        # receive data
        jsn_s = clientsocket.recv(2**16)
        print(f"received jsn_s = {len(jsn_s)}")
        try:
            packet = pickle.loads(jsn_s)
        except:
            continue
        print(f"data received source:{packet[0]} destinaiton{packet[1]}")
        destsock = None
        for cl in all_clients:
            if cl[-1] == packet[1]:
                destsock = cl
        if destsock is None:
            print("\tINVALID CLIENT")
        else:
            print(f"\tdata sent to {destsock[-1]}")
            destsock[0][0].send(jsn_s)




# will we create threads dynamically
# each new connection causes a new thread to be created
serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
print(f"binding socket on {SOCK_IP}:{SOCK_PORT}")
serversocket.bind((SOCK_IP, SOCK_PORT))
serversocket.listen(3)

# now connect to the web server on port 80 - the normal http port
while True:
    try:
        client_id = (serversocket.accept(),)
        thrd1 = Thread(target=client_handler, args=client_id)
        thrd1.start()
    except KeyboardInterrupt:
        serversocket.close()
        break



# allow async connections
# the architecture of the server needs to be such that multiple clients can connect to it
# without them affecting other connections


# client is sending and receiving audio in parallel
# server is receiving packets and immediately forwarding them to the other side concurrently


# first start with a minimum number of connected users (2)

# disable socket connections


print("server has ended")