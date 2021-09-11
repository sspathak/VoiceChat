from threading import Thread, Lock, Condition
import socket
import sounddevice as sd
from time import sleep
import pickle
import numpy as np
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from socket import timeout

MAX_BYTES_SEND = 512  # Must be less than 1024 because of networking limits
MAX_HEADER_LEN = 20  # allocates 20 bytes to store length of data that is transmitted
print("client started")
print("_________________________________________________________________________________")

# client sends self id
# client sends recipient's id
# client sends data

# socket connect to the server


SERVER_IP = '0.0.0.0'  # Change this to the external IP of the server

SERVER_PORT = 9001
BUFMAX = 512
running = True
mutex_t = Lock()
item_available = Condition()
SLEEPTIME = 0.0001  # amount of time CPU sleeps between sending recordings to the server
# SLEEPTIME = 0.000001
audio_available = Condition()

sdstream = sd.Stream(samplerate=44100, channels=1, dtype='float32')
sdstream.start()

key = b'thisisthepasswordforAESencryptio'
iv = get_random_bytes(16)
cipher = AES.new(key, AES.MODE_CBC, iv)


def get_iv():
    return get_random_bytes(16)


def decrypt(enc_data):
    cphr = AES.new(key, AES.MODE_CBC, enc_data[:16])
    decoded = cphr.decrypt(enc_data)[16:]
    return decoded.rstrip()


def encrypt(data_string):
    iv = get_iv()
    # cphr = AES.new(key, AES.MODE_CBC, iv)
    d = iv + data_string
    d = (d + (' ' * (len(d) % 16)).encode())
    return cipher.encrypt(d)


def split_send_bytes(s, inp):
    data_len = (len(inp))
    if data_len == 0:
        print('ERROR: trying to send 0 bytes')  # should not happen in theory but threads are weird
        return

    # tells the client on the other end how many bytes it's expecting to receive
    header = str(data_len).encode('utf8')
    header_builder = b'0' * (MAX_HEADER_LEN - len(header)) + header
    s.send(header_builder)

    # send content in small batches. Maximum value of MAX_BYTES_SEND is 1024
    for i in range(data_len // MAX_BYTES_SEND):
        s.send(inp[i * MAX_BYTES_SEND:i * MAX_BYTES_SEND + MAX_BYTES_SEND])

    # send any remaining data
    if data_len % MAX_BYTES_SEND != 0:
        s.send(inp[-(data_len % MAX_BYTES_SEND):])


def split_recv_bytes(s):
    dat = b''

    # receive header that specifies number of incoming bytes
    data_len_raw = s.recv(MAX_HEADER_LEN)
    try:
        data_len = int((data_len_raw).decode('utf8'))
    except UnicodeDecodeError as e:
        print(data_len_raw)
        raise e
    while data_len == 0:
        print(f"received 0 bytes. raw = {data_len_raw}")  # should never happen
        data_len = int((s.recv(MAX_BYTES_SEND)).decode('utf8'))

    # read bytes
    for i in range(data_len // MAX_BYTES_SEND):
        dat += s.recv(MAX_BYTES_SEND)
    if data_len % MAX_BYTES_SEND != 0:
        dat += s.recv(data_len % MAX_BYTES_SEND)

    return dat


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
    global running
    if running:
        return sdstream.read(t)[0]


def transmit(buf, socket):
    global running
    pickled = buf.tobytes()
    encrypted_str = encrypt(pickled)

    try:
        split_send_bytes(socket, encrypted_str)
    except timeout:
        print("SOCKET TIMEOUT")
        running = False
    except BrokenPipeError:
        print("Recipient disconnected")
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
    tr_thread = Thread(target=transmitter_consumer, args=(tbuf, serversocket))

    rec_thread.start()
    tr_thread.start()

    rec_thread.join()
    tr_thread.join()
    return


# use a sound library to play the buffer
def play(buf):
    # print("playing_audio")
    global running
    if running:
        sdstream.write(buf)


def receive(socket):
    global running
    while running:
        try:
            dat = split_recv_bytes(socket)
            dat = decrypt(dat)
            buf = np.frombuffer(dat, dtype='float32')  # read decrypted numpy array
            yield buf
        except pickle.UnpicklingError as e:
            print(f"    @@@@@ UNPICKLE ERROR @@@@@   \n DATA RECEIVED {len(dat)} :: {dat}")  # INPUT______ of len = {sys.getsizeof(dat)} ::{decrypt(dat)} :: {str(e)}")
            continue
        except timeout:
            print("SOCKET TIMEOUT")
            yield None
        except ConnectionResetError:
            print("Recipient disconnected")
            yield None


def receive_play_thread(serversocket):
    print("***** STARTING RECEIVE PLAY THREAD *****")
    rbuf = SharedBuf()

    def receiver_producer(buff, serversocket):
        global running
        rece_generator = receive(serversocket)
        while running:
            sleep(SLEEPTIME)
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

    rece_thread = Thread(target=receiver_producer, args=(rbuf, serversocket))
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
    sdstream.stop()
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
    print(f"message length = {len((source_name + (' ' * (512 - len(source_name)))).encode())}")
    s.send((source_name + (' ' * (512 - len(source_name)))).encode())

    destination_name = str(input("enter destination name :"))
    s.send((destination_name + (' ' * (512 - len(destination_name)))).encode())
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
