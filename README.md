# VoiceChat
an encrypted voice chat app, written in Python, that uses websockets to send data between a multi-threaded client and server

# Setup
- install python-sounddevice `python3 -m pip install sounddevice --user`
- install numpy `pip install numpy`

# Client
The client creates two threads - record-transmit and recieve-play.
Each thread creates two more threads that simultaneously fill and empty a shared buffer
- record-transmit: recorder (producer) transmitter (consumer) share one buffer
- receive-play: receiver (producer) player (consumer) share one buffer

uses sounddevice module to read and write to an audio stream (https://python-sounddevice.readthedocs.io/en/0.4.0/#)
uses Python's threading module to manage threads and enable concurrency

# Server
Creates a Client object whenever a user connects to the server
- Each connected client gets its own thread
- Client specifies its own identifier and recipient

Once both the clients (source) are connected and have each other as recipients (destination), the server enters conversation mode
In conversation mode, all data received from one source is directly sent over to the destination.
