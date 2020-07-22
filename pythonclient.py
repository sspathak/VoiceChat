print("client started")
print("_________________________________________________________________________________")

# client sends self id
# client sends recipient id
# client sends data


from threading import Thread, Lock, Condition
import json
import sys
import socket
import sounddevice as sd
from time import sleep
import pickle
import numpy as np
# socket connect to the server



SERVER_IP = '35.237.61.15'
# SERVER_IP = '0.0.0.0'
SERVER_PORT = 9001
BUFMAX = 512
running = True
mutex_t = Lock()
item_available = Condition()
SLEEPTIME = 0.0001
audio_available = Condition()

sdstream = sd.Stream(samplerate=44100, channels=1, dtype='float32')
sdstream.start()




class SharedBuf:
    def __init__(self):
        self.buffer = np.array([], dtype='float32')

    def clearbuf(self):
        self.buffer = []

    def addbuf(self, arr):
        self.buffer = np.append(self.buffer, arr)
    def extbuf(self, arr):
        self.buffer = np.append(self.buffer, arr)
    def getlen(self):
        return len(self.buffer)
    def getbuf(self):
        return self.buffer
    def getx(self, x):
        data = self.buffer[0:x]
        self.buffer = self.buffer[x:]
        return data


def record(t):
    # record t seconds of audio
    recorded_array = sdstream.read(t)
    # print(f"\t\t\t\t\t\t\tAUDIO_INPUT______:{len(recorded_array[0])}")
    return recorded_array[0]


def transmit(buf, socket):
    # buf = [0]*10
    packet = buf
    jsn = pickle.dumps(packet)
    # print(f"_____OUTPUT of length = {sys.getsizeof(jsn)}B, {len(jsn)}Chars")
    socket.send(jsn)


def record_transmit_thread(serversocket):
    # maintains a transmit buffer
    print("***** STARTING RECORD TRANSMIT THREAD *****")
    tbuf = SharedBuf()
    global running

    def recorder_producer(buf):
        while running:
            # print("!!! reco loop !!!")
            # sleep(0.1)
            sleep(SLEEPTIME)
            data = record(32)
            with item_available:
                item_available.wait_for(lambda: buf.getlen() <= BUFMAX)
                # produce() # record audio
                # buf.addbuf(data)
                buf.extbuf(data)
                item_available.notify()
        print("RECORDER ENDS HERE")

    def transmitter_consumer(buf, serversocket):
        while running:
            # print("!!! tran loop !!!")
            # sleep(0.1)
            sleep(SLEEPTIME)
            with item_available:
                # print(f"buffer len = {buf.getlen()}")
                item_available.wait_for(lambda: buf.getlen() >= 32)
                # print(f"length of buffer before transmission = {buf.getlen()}")
                # consume() # send audio

                transmit(buf.getx(32), serversocket)
                item_available.notify()
                # buf.clearbuf()
        print("TRANSMITTER ENDS HERE")


    rec_thread = Thread(target=recorder_producer, args=(tbuf,))
    tr_thread = Thread(target=transmitter_consumer, args=(tbuf,serversocket))

    rec_thread.start()
    tr_thread.start()

    rec_thread.join()
    tr_thread.join()
    return


def play(buf):
    # use a sound library to play the buffer
    print(f"\t\t\t\t\t\t\tAUDIO______OUTPUT: {len(buf)}")
    sdstream.write(buf)


def receive_play_thread(serversocket):
    # maintains a play buffer
    print("***** STARTING RECEIVE PLAY THREAD *****")
    rbuf = SharedBuf()
    def receiver_producer(buff, serversocket):
        jsn = b''
        while running:
            # print("!!! recv loop !!!")
            # sleep(1)
            sleep(SLEEPTIME)
            while sys.getsizeof(jsn) < 314:
                jsn += serversocket.recv(281)

            try:
                buf = pickle.loads(jsn[:281])
            except pickle.UnpicklingError:
                print("@@@@@ UNPICKLE ERROR @@@@@")
                print(f"INPUT______ of len = {sys.getsizeof(jsn)} ::{jsn[:281]}")
            jsn = jsn[281:]

            with audio_available:
                print(f">>>>>>>>>>receiver acquired lock. buf length = {buff.getlen()}")

                audio_available.wait_for(lambda: buff.getlen() <= BUFMAX)
                # produce() # receive audio
                # print(buf)
                buff.extbuf(buf)
                audio_available.notify()
            print(f"<<<<<<<<<<receiver released lock. buf length = {buff.getlen()}")
        print("RECEIVER ENDS HERE")

    def player_consumer(buff):
        while running:
            # print("!!! play loop !!!")
            # sleep(1)
            sleep(SLEEPTIME)
            # b = []
            with audio_available:
                print(f">>>>>>>>>>player acquired lock. buf length = {buff.getlen()}")
                # print(f"PLAYER BUF LEN = {buff.getlen()}")
                audio_available.wait_for(lambda: buff.getlen() >= 32)
                # consume() # play audio
                # b.extend(buff.getx(32))

                play(buff.getx(buff.getlen()))
                audio_available.notify()
                # buff.clearbuf()
            # play(b)
            print(f"<<<<<<<<<<player released lock. buf length = {buff.getlen()}")
        print("PLAYER ENDS HERE")

    global running

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
    global destination_name
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((SERVER_IP, SERVER_PORT))

    source_name = str(input("enter source name :"))
    print(f"hello {source_name}")
    print(f"message length = {len((source_name + (' '*(512-len(source_name)))).encode())}")
    s.send((source_name + (' '*(512-len(source_name)))).encode())

    destination_name = str(input("enter destination name :"))
    s.send((destination_name + (' '*(512-len(destination_name)))).encode())
    sleep(2)
    val = s.recv(2)
    if val.decode() != 'go':
        raise TypeError
    # returns socket fd
    return s


main()
# 2 separate websocket connections for receiving and sending files
# 2 separate threads to handle transmission and playback of the audio files


# start recording and keep sending data


# disconnect server


print("client terminating")