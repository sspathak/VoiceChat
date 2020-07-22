# VoiceChat
a Python voice chat app that uses websockets to send data between a multi-threaded client and server

# Client
Two threads: record-transmit and recieve-play
each thread creates two more threads that simultaneously fill and expty a buffer
record-transmit: recorder (producer) transmit (consumer)
receive-play: receiver (producer) plater (consumer)

# Server
Each connected client gets its own thread
Client specifies its own identifier and recipient
Once both the clients (source) are connected and have each other as recipients (destination), the server enters conversation mode
In conversation mode, all data received from one source is directly sent over to the destination.
