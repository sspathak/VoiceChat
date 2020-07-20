print("client started")

from threading import Thread, Lock, Condition
import json
import sys
import socket
import sounddevice as sd
from time import sleep
import pickle
import numpy as np
# socket connect to the server

source_name = str(input("enter source name"))
print(f"hello {source_name}")
destination_name = str(input("enter destination name"))
SERVER_IP = '0.0.0.0'
SERVER_PORT = 9000
running = True
mutex_t = Lock()
item_available = Condition()

audio_available = Condition()

sdstream = sd.Stream(samplerate=44100, channels=1, dtype='float32')
sdstream.start()




class SharedBuf:
    def __init__(self):
        self.buffer = []

    def clearbuf(self):
        self.buffer = []

    def addbuf(self, arr):
        self.buffer.append(arr)
    def getlen(self):
        return len(self.buffer)
    def getbuf(self):
        return self.buffer

def record(t):
    # record t seconds of audio
    recorded_array = sdstream.read(int(t*44100))
    return recorded_array

def transmit(buf, socket):
    packet = (source_name, destination_name, buf)
    jsn = pickle.dumps(packet)
    print(f"\tsending packet of size = {sys.getsizeof(jsn)}B from {source_name} to {destination_name}")
    socket.send(jsn)

def record_transmit_thread(serversocket):
    # maintains a transmit buffer
    tbuf = SharedBuf()
    global running
    def recorder_producer(buf):
        while running:
            sleep(0.01)
            data = record(0.1)
            with item_available:
                # produce() # record audio
                buf.addbuf(data)
                item_available.notify()

    def transmitter_consumer(buf, serversocket):
        while running:
            sleep(0.01)
            with item_available:
                item_available.wait_for(lambda: buf.getlen() > 0)
                # consume() # send audio
                transmit(buf.getbuf(), serversocket)
                buf.clearbuf()


    rec_thread = Thread(target=recorder_producer, args=(tbuf,))
    tr_thread = Thread(target=transmitter_consumer, args=(tbuf,serversocket))

    rec_thread.start()
    tr_thread.start()

    rec_thread.join()
    tr_thread.join()
    return



def play(buf):
    # use a sound library to play the buffer
    # buf = np.array(buf[0][0])
    # buf = buf.reshape((-1, 1))
    # print(buf)
    # print(buf.shape)
    sdstream.write(buf[0][0])
    # sd.play(buf, 44100)
    # sleep(0.1)
    # sd.wait()


def receive_play_thread(serversocket):
    # maintains a play buffer

    rbuf = SharedBuf()


    def receiver_producer(buff, serversocket):
        while running:
            sleep(0.01)
            with audio_available:
                # produce() # receive audio
                jsn = serversocket.recv(2**16)

                src_n, dst_n, buf = pickle.loads(jsn)
                print(f"\t\t\t\t\t\tdata received from {src_n}, dest {dst_n} data:{len(buf)}")
                buff.addbuf(buf[0])
                audio_available.notify()


    def player_consumer(buff):
        while running:

            sleep(0.01)
            with audio_available:
                audio_available.wait_for(lambda: buff.getlen() > 0, timeout=0.1)
                # consume() # play audio
                play(buff.getbuf())
                print("\t\t\t\t\t\tplayer_running")
                buff.clearbuf()

    global running
    # while running:
    #     sleep(0.05)
    #     try:
    #         receiver_producer(rbuf, serversocket)
    #         player_consumer(rbuf)
    #         rbuf.clearbuf()
    #     except KeyboardInterrupt:
    #         serversocket.close()
    #         break

    rece_thread = Thread(target=receiver_producer,args=(rbuf, serversocket))
    play_thread = Thread(target=player_consumer, args=(rbuf,))

    rece_thread.start()
    play_thread.start()

    rece_thread.join()
    play_thread.join()

    return



def main():
    serversocket = connect()
    try:

        t_thread = Thread(target=record_transmit_thread, args=(serversocket,))
        # start thread record_transmit
        p_thread = Thread(target=receive_play_thread, args=(serversocket,))
        # start thread receive_play

        t_thread.start()
        p_thread.start()
    except KeyboardInterrupt:
        serversocket.close()
        global running
        running = False
        return
    t_thread.join()
    p_thread.join()

def connect():
    global source_name
    global SERVER_IP
    global SERVER_PORT
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((SERVER_IP, SERVER_PORT))
    s.send(source_name.encode())

    # returns socket fd
    return s

main()
# 2 separate websocket connections for receiving and sending files
# 2 separate threads to handle transmission and playback of the audio files


# start recording and keep sending data


# disconnect server


print("client terminating")