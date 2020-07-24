from time import sleep
from threading import Thread, Lock, Condition
import pickle
import socket

SOCK_IP = '10.142.0.2'
SOCK_PORT = 9001

class Client:
    allClients = []
    availableClients = {}  # {'client name' : client object}


    def __init__(self, client_ptr):
        Client.allClients.append(self)
        self.cl_ptr = client_ptr
        self.name = None
        self.name = self.get_name()
        self.recipient_name = None
        self.recipient_name = self.get_recipient_name()
        print(f"received name {self.name} and recipient {self.recipient_name}")
        Client.availableClients[self.name] = self
        try:
            self.lobby()
        except ConnectionResetError:
            print("CONNECTION RESET ERROR")
            self.close()
        except BrokenPipeError:
            print("BROKEN PIPE. Closing connection")
            self.close()

    def lobby(self):
        cl = None
        while True:
            try:
                cl = Client.availableClients[self.recipient_name]
                if cl.get_recipient_name() == self.name:
                    break
                else:
                    print("recipient busy.")
                    sleep(1)
            except KeyError:
                print("waiting...")
                sleep(1)
                continue
        if cl is not None:
            # found a client who wants to connect to self
            self.cl_ptr[0].send('go'.encode())
            self.converse(cl)
        self.close()

    # Enter a loop to keep searching for recipient in available clients

    def get_name(self):
        if self.name is None:
            # receive name
            self.name = self.cl_ptr[0].recv(512).decode().rstrip()
            print(f"Client connected: {self.name}")
        return self.name

    def get_recipient_name(self):
        if self.recipient_name is None:
            # receive recipient name
            self.recipient_name = self.cl_ptr[0].recv(512).decode().rstrip()
            print(f"Client {self.name} wants to connect to {self.recipient_name}")
        return self.recipient_name

    # def getRecipientSocket(self):
    #     search list of available clients

    def converse(self, recipient_obj):
        print("establishing connection...")
        try:
            while True:
                self.send(recipient_obj, self.read())
        except KeyboardInterrupt:
            self.close()

    def send(self, cl_object, data):
        cl_object.cl_ptr[0].send(data)

    def read(self):
        return self.cl_ptr[0].recv(1024)

    def close(self):
        Client.allClients.remove(self)
        Client.availableClients.pop(self.get_name(), None)
        self.cl_ptr[0].close()

def main():
    serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print(f"binding socket on {SOCK_IP}:{SOCK_PORT}")
    serversocket.bind((SOCK_IP, SOCK_PORT))
    serversocket.listen(3)

    while True:
        try:
            client_id = (serversocket.accept(),)
            thrd1 = Thread(target=client_handler, args=client_id)
            thrd1.start()
        except KeyboardInterrupt:
            serversocket.close()
            break

def client_handler(clientid):
    Client(clientid)

main()
