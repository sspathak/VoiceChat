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
import random
from Crypto.Cipher import AES
from socket import timeout
# socket connect to the server



SERVER_IP = '35.237.61.15'
# SERVER_IP = '0.0.0.0'
SERVER_PORT = 9001
BUFMAX = 512
running = True
mutex_t = Lock()
item_available = Condition()
# SLEEPTIME = 0.00001
SLEEPTIME = 0.000001
audio_available = Condition()

sdstream = sd.Stream(samplerate=44100, channels=1, dtype='float32')
sdstream.start()

key = b'thisisthepasswordforAESencryptio'
# random.seed(input("ENTER RANDOM SEED :"))
random.seed('changethisrandomseed')
# iv_seed = hash(hash(key))
# random.seed(iv_seed)
iv = ''.join([chr(random.randint(0, 0xFF)) for i in range(16)])
iv = iv.encode()
cipher = AES.new(key, AES.MODE_CBC, iv[:16])
# nonce = cipher.nonce
# ciphertext, tag = cipher.encrypt_and_digest(data)
def get_iv():
    return (''.join([chr(random.randint(0, 0xFF)) for i in range(16)])).encode()[:16]

def decrypt(enc_data):
    cphr = AES.new(key, AES.MODE_CBC, enc_data[:16])
    decoded = cphr.decrypt(enc_data)[16:]
    return decoded.rstrip()

def encrypt(data_string):
    iv = get_iv()
    cphr = AES.new(key, AES.MODE_CBC, iv)
    d = iv + data_string
    d = (d + (' ' * (len(d) % 16)).encode())
    d = d[:(0 - (len(d) % 16))]

    return cipher.encrypt(d)

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


# record t seconds of audio
def record(t):
    recorded_array = sdstream.read(t)
    return recorded_array[0]


def transmit(buf, socket):
    # print(f"PICKLED VAL ____ = {pickle.dumps(buf)}")
    pickled = pickle.dumps(buf)
    # print(f"PICKLED ______ =  {pickled}")
    encrypted_str = encrypt(pickled)
    # decrypted = decrypt(encrypted_str)
    # print(f"PICKLED ___ENC = {decrypted}")
    try:
        socket.send(encrypted_str)
    except timeout:
        print("SOCKET TIMEOUT")
        global running
        running = False


def record_transmit_thread(serversocket):
    print("***** STARTING RECORD TRANSMIT THREAD *****")
    tbuf = SharedBuf()
    global running

    def recorder_producer(buf):
        global running
        while running:
            sleep(SLEEPTIME)
            data = record(32)
            with item_available:
                item_available.wait_for(lambda: buf.getlen() <= BUFMAX)
                buf.extbuf(data)
                item_available.notify()

        print("RECORDER ENDS HERE")

    def transmitter_consumer(buf, serversocket):
        global running
        while running:
            sleep(SLEEPTIME)
            with item_available:
                item_available.wait_for(lambda: buf.getlen() >= 32)
                transmit(buf.getx(32), serversocket)
                item_available.notify()

        print("TRANSMITTER ENDS HERE")

    rec_thread = Thread(target=recorder_producer, args=(tbuf,))
    tr_thread = Thread(target=transmitter_consumer, args=(tbuf,serversocket))

    rec_thread.start()
    tr_thread.start()

    rec_thread.join()
    tr_thread.join()
    return


# use a sound library to play the buffer
def play(buf):
    # print("playing_audio")
    sdstream.write(buf)

def receive(socket):
    jsn = b''
    while running:
        while (len(jsn) < 304) and running:
            try:
                jsn += socket.recv(304)
            except timeout:
                print("SOCKET TIMEOUT")
                yield None

        try:
            dat = jsn[:304]
            # print(len(dat))
            # print(len(dat) % 16)
            dat = decrypt(dat)
            # print(f"DATA RECEIVED = {dat}")
            buf = pickle.loads(dat)

        except pickle.UnpicklingError:
            print(f"    @@@@@ UNPICKLE ERROR @@@@@    INPUT______ of len = {sys.getsizeof(jsn)} ::{decrypt(jsn[:304])}")
            continue
        jsn = jsn[304:]
        yield buf

def receive_play_thread(serversocket):
    print("***** STARTING RECEIVE PLAY THREAD *****")
    rbuf = SharedBuf()

    def receiver_producer(buff, serversocket):
        global running
        rece_generator = receive(serversocket)
        while running:
            sleep(SLEEPTIME)
            # while sys.getsizeof(jsn) < 314:
            try:
                data = next(rece_generator)
            except StopIteration:
                break
            if data is None:
                break
            with audio_available:
                audio_available.wait_for(lambda: buff.getlen() <= BUFMAX)
                buff.extbuf(data)
                audio_available.notify()

        print("RECEIVER ENDS HERE")

    def player_consumer(buff):
        while running:
            sleep(SLEEPTIME)
            with audio_available:
                audio_available.wait_for(lambda: buff.getlen() >= 32)
                play(buff.getx(buff.getlen()))
                audio_available.notify()

        print("PLAYER ENDS HERE")

    global running

    rece_thread = Thread(target=receiver_producer,args=(rbuf, serversocket))
    play_thread = Thread(target=player_consumer, args=(rbuf,))
    rece_thread.start()
    play_thread.start()
    # input("press enter to exit")
    # running = False

    rece_thread.join()
    play_thread.join()
    return


def main():
    serversocket = connect()
    global running
    t_thread = Thread(target=record_transmit_thread, args=(serversocket,))
    p_thread = Thread(target=receive_play_thread, args=(serversocket,))
    t_thread.start()
    p_thread.start()
    input("press enter to exit")
    running = False
    t_thread.join()
    p_thread.join()
    serversocket.close()


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
    s.settimeout(5.0)
    return s


main()
# 2 separate websocket connections for receiving and sending files
# 2 separate threads to handle transmission and playback of the audio files


# start recording and keep sending data


# disconnect server


print("client terminating")