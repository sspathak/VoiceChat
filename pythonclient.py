from threading import Thread, Lock, Condition
import socket
import sounddevice as sd
from time import sleep
import numpy as np
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from socket import timeout
from Crypto.Util.Padding import pad, unpad

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
running = True
item_available = Condition()
# amount of time CPU sleeps between sending recordings to the server
SLEEPTIME = 0.001
AUDIO_DTYPE = 'float32'
audio_available = Condition()
# number of bytes to send over network in one go
TX_BATCH_SIZE = 64
# number of samples to record
RECORDING_SIZE = TX_BATCH_SIZE*2
# sample rate of the audio
SAMPLE_RATE = 44100
# size of the shared buffer
SHARED_BUF_SIZE = RECORDING_SIZE*64
# player consumer will wait until this many bytes are available in the buffer before playing
PLAYER_READ_LAG_SIZE = RECORDING_SIZE*32
# number of bytes to read from the buffer for playback
PLAYER_READ_BYTE_SIZE = RECORDING_SIZE


assert(PLAYER_READ_LAG_SIZE >= PLAYER_READ_BYTE_SIZE)
assert(SHARED_BUF_SIZE >= PLAYER_READ_LAG_SIZE)
assert(RECORDING_SIZE <= SHARED_BUF_SIZE)

sdstream = sd.Stream(samplerate=SAMPLE_RATE, channels=1, dtype=AUDIO_DTYPE)
sdstream.start()

key = b'thisisthepasswordforAESencryptio'
iv = get_random_bytes(16)
cipher = AES.new(key, AES.MODE_CBC, iv)
cphr = None


def get_iv():
    return get_random_bytes(16)


def decrypt(enc_data):
    global cphr
    if cphr is None:
        cphr = AES.new(key, AES.MODE_CBC, enc_data[:16])
    # decoded = cphr.decrypt(enc_data)[16:]
    decoded = unpad(cphr.decrypt(enc_data)[16:], AES.block_size)
    return decoded.rstrip()


def encrypt(data_string):
    iv = get_iv()
    # cphr = AES.new(key, AES.MODE_CBC, iv)
    d = iv + data_string
    d = (d + (' ' * (len(d) % 32)).encode())
    return cipher.encrypt(pad(d, AES.block_size))


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
        # print(data_len_raw)
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
    def __init__(self, size=0):
        self.size = size
        self.read_cursor = 0
        self.write_cursor = 0
        self.buffer = np.array([0] * size, dtype=AUDIO_DTYPE)

    def clearbuf(self):
        self.buffer = np.array([0] * self.size, dtype=AUDIO_DTYPE)
        self.read_cursor = 0
        self.write_cursor = 0

    def extbuf(self, arr):
        arr = arr.reshape(-1)
        arr_len = len(arr)
        # if ar is too long, truncate it
        if arr_len > self.size:
            arr = arr[-self.size:]
            arr_len = self.size
        # loop around the buffer if not enough space
        if arr_len + self.write_cursor > self.size:
            self.buffer[self.write_cursor:] = arr[:self.size - self.write_cursor]
            self.buffer[:arr_len - (self.size - self.write_cursor)] = arr[self.size - self.write_cursor:]
        else:
            self.buffer[self.write_cursor:self.write_cursor + arr_len] = arr
        # update write cursor
        self.write_cursor = (self.write_cursor + arr_len) % self.size

    def getlen(self):
        if self.write_cursor >= self.read_cursor:
            return self.write_cursor - self.read_cursor
        else:
            return self.size - self.read_cursor + self.write_cursor

    def getbuf(self):
        return self.buffer

    def getx(self, x):
        # read x bytes from the buffer
        if self.read_cursor + x > self.size:
            ret = np.append(self.buffer[self.read_cursor:], self.buffer[:self.read_cursor + x - self.size])
        else:
            ret = self.buffer[self.read_cursor:self.read_cursor + x][:]
        self.read_cursor = (self.read_cursor + x) % self.size
        return ret



# record t bytes of audio
def record(t):
    global running
    if running:
        recorded = sdstream.read(t)[0]
        return recorded


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
    tbuf = SharedBuf(SHARED_BUF_SIZE)
    global running

    def recorder_producer(buf):
        global running
        while running:
            sleep(SLEEPTIME/100)
            # record does not need a lock because it is not a shared resource
            data = record(RECORDING_SIZE)
            if data is not None:
                with item_available:
                    # if buffer is full, wait for it to be emptied
                    if item_available.wait_for(lambda: buf.getlen() <= SHARED_BUF_SIZE, timeout=2):
                        buf.extbuf(data)
                    item_available.notify()
        print("RECORDER ENDS HERE")

    def transmitter_consumer(buf, serversocket):
        global running
        while running:
            sleep(SLEEPTIME)
            with item_available:
                # if buffer is empty, wait for it to be filled
                item_available.wait_for(lambda: buf.getlen() >= TX_BATCH_SIZE, timeout=2)
                payload = buf.getx(TX_BATCH_SIZE)
                item_available.notify()
            transmit(payload, serversocket)

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
    global running
    if running:
        sdstream.write(buf)


prev_receive = -1
def receive(socket):
    global running
    buf = None
    while running:
        try:
            dat = split_recv_bytes(socket)
            dat = decrypt(dat)
            buf = np.frombuffer(dat, dtype=AUDIO_DTYPE)  # read decrypted numpy array
            yield buf
        except timeout:
            print("SOCKET TIMEOUT")
            yield None
        except ValueError:
            yield buf
        except ConnectionResetError:
            print("Recipient disconnected")
            yield None


def receive_play_thread(serversocket):
    print("***** STARTING RECEIVE PLAY THREAD *****")
    rbuf = SharedBuf(SHARED_BUF_SIZE)

    def receiver_producer(buff, serversocket):
        global running
        rece_generator = receive(serversocket)

        data = None
        while running:
            sleep(SLEEPTIME)
            try:
                data = next(rece_generator)
            except StopIteration:
                pass

            if data is None:
                continue
            with audio_available:
                # producer does not wait for the buffer to be emptied and just overwrites it if it is full
                buff.extbuf(data)
                audio_available.notify()

        print("RECEIVER ENDS HERE")

    def player_consumer(buff):
        while running:
            sleep(SLEEPTIME/100)

            with audio_available:
                if buff.getlen() < PLAYER_READ_BYTE_SIZE:
                    # if buffer is empty, wait for it to be filled
                    audio_available.wait_for(lambda: buff.getlen() >= PLAYER_READ_LAG_SIZE, timeout=2)
                read_aud = buff.getx(PLAYER_READ_BYTE_SIZE)
            # playback does not need a lock because it is not a shared resource
            play(read_aud)

        print("PLAYER ENDS HERE")

    global running

    rece_thread = Thread(target=receiver_producer, args=(rbuf, serversocket))
    play_thread = Thread(target=player_consumer, args=(rbuf,))
    rece_thread.start()
    play_thread.start()
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
