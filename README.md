# VoiceChat
An encrypted voice chat app, written in Python, that uses websockets to send data between a multi-threaded client and server

# Setup
- install python-sounddevice `python3 -m pip install sounddevice --user`
- install numpy `pip install numpy`

## How do I put the server on the internet?
- [YouTube Video link](https://www.youtube.com/watch?v=EIVwWbLopVw)
### GCP instructions
- Create a new compute engine instance - for example N1 Series' F1 Micro - on GCP (*It's free!)
- In firewall settings, allow access to port 9001 (and any other port that is being used in the Python server code)
- Install Python 3.7+ and pip3   on the server ([link](https://tecadmin.net/how-to-install-python-3-9-on-ubuntu-18-04/), [link](https://linuxize.com/post/how-to-install-pip-on-ubuntu-18.04/))
- Clone this repository onto the server
- Install dependencies using `pip3 install -r requirements.txt`
- Update PYTHONPATH with `export PYTHONPATH=$PYTHONPATH:/path/to/VoiceChat`
- Run the Python server script
-- NOTE: you might have to update the SOCK_IP address (line 6, pythonserver.py)

Now, the server should be up and running!
- Next, clone this repository onto your PC and update the pythonclient.py file with the "External IP adderss" of your compute engine VM
- You can also change the encryption password
- Run the client and follow the instrucitons to pick a user ID for the client. Then enter the recipient's ID
- Repeat the above step for a second client instance and assign it the user ID entered for recipient ID above. The recipient for this client will be the user ID of the client from the previous step. In other words: user ABC wishes to call user XYZ, and user XYZ wishes to call user ABC.
- The server should print "establishing connection..." after which the clients can engage in conversation.
 
  
_*NOTE: Only 1 GB of free network traffic is permitted on GCP after which you will have to pay if you wish to use more data._

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


