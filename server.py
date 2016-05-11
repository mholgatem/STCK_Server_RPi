#! /usr/bin/env python
import SocketServer, subprocess, sys 
import threading
import thread
import time
import evdev
from evdev import InputDevice, list_devices, InputEvent, ecodes as e, UInput
import json
import keys
import broadcast
import argparse
import signal
import screencap
import base64
import AESCipher


'''
SET ARGUMENT OPTIONS
--------------------
--max_users - Allow multiple users to connect. 1 instance of server.py + multiple handler threads (1 per user)
--port - Server Port number to use, will increment per user
--bcastport - Port to listen for client broadcast invitations
--bcastip - ip address to listem for client broadcast invitations
--key - Secret key to use to encrypt/decrypt. must be same in client
--debug - output info to console for debugging purposes
'''

parser = argparse.ArgumentParser(description='STCKServer')
parser.add_argument('--max_users', 
						metavar = '4', default = 4, type = int,
						help='Maximum number of server threads to run.')
parser.add_argument('--packet_size', 
						metavar = '1024', default = 1024, type = int,
						help='packet size to send/receive')                        
parser.add_argument('--port',
						metavar = '2000', default = 2000, type = int,
						help='Starting port number. Port range = port + max_users')
parser.add_argument('--bcastport',
						metavar = '55535', default = 55535, type = int,
						help='Listen for broadcast invitations on this port')
parser.add_argument('--bcastip',
						metavar = '255.255.255.255', default = '255.255.255.255',
						type = str, help='Listen for broadcast invitations on this IP')
parser.add_argument('--key',
						metavar = '', default = '*4kap),dci30dm?',
						type = str, help='Secret Encryption Key')
parser.add_argument('--debug',
                        default = False, action='store_true',
                        help='Print data pertaining to current processes')
parser.add_argument('--disable_encryption',
                        default = False, action='store_true',
                        help='Disable encryption for all commands (excludes broadcasts)')
                        
						
args = parser.parse_args()
args.salt = 'a$fk^fkj69)-YU' #DO NOT CHANGE WITHOUT ALTERING CLIENT CODE AS WELL!

HOST = '0.0.0.0'
PORT = args.port
SCREENCAPIMAGE = ''

'''
INITIALIZE EVDEV KEYBOARD/JOYSTICKS
'''
keylist = [ value for key, value in keys.keyList.iteritems() ]
cap = {
        e.EV_KEY : keylist,
        e.EV_ABS : [
            (e.ABS_X, [-32767, 32767, 3, 1, 5, 6]),
            (e.ABS_Y, [-32767, 32767, 3, 1, 5, 6]),
            ]
}
    

''' Future capability to run commands '''
''' example: reply = pipe_command(my_unix_command, data)'''
def pipe_command(arg_list, standard_input=False):
    "arg_list is [command, arg1, ...], standard_input is string"
    pipe = subprocess.PIPE if standard_input else None
    subp = subprocess.Popen(arg_list, stdin=pipe, stdout=subprocess.PIPE)
    if not standard_input:
        return subp.communicate()[0]
    return subp.communicate(standard_input)[0]

'''doKey(ecodes.EV_KEY,ecodes.KEY_UP)'''
def doKey(inputKey, pressedState):
    ev = InputEvent(time.time(), 0, e.EV_KEY, inputKey, pressedState)
    #with UInput() as ui:
    ui.write_event(ev)
    ui.syn()

def setAxis(value):
    xAxis = value[0]
    yAxis = value[1]
    ui.write(e.EV_ABS, e.ABS_X, int(xAxis))
    ui.write(e.EV_ABS, e.ABS_Y, int(yAxis))
    ui.syn()
    
def signal_handler(signal, frame):
    sys.exit(0)
    
def debug(debugMessage):
    if args.debug:
        print '-----------------------'
        print debugMessage
        
def startNewServer():
    print "testing:"
    
class SingleTCPHandler(SocketServer.BaseRequestHandler):


    RUNNING = True;
    STREAMING = False;
    screencap.init(quality = 80, height = 320, width = 240, rate=.03);
    aes = AESCipher.AESCipher(args.key, args.salt, args.disable_encryption)
    startNewServer()
    
    def handle(self):
        # self.request is the client connection
        
        debug("Connected to {0} on port {1}".format(*self.client_address))
        
        while self.RUNNING:
            data = self.aes.decrypt(self.request.recv(args.packet_size))  # clip input at 1Kb
            if not data:
                break
            if 'exit' in data:
                break
            #decode data
            dataChunks = json.loads(data)
            '''
            authCode not really necessary with tcp.
            if using udp, respond to client with authcode
            so that client knows data was received
            '''
            authCode = dataChunks.keys()[0]
            for d in dataChunks[authCode]:
                try:
                    self.handleType(d)
                except ValueError:
                    debug("Data from {0} had a ValueError".format(self.client_address[0]))
            
            #self.request.send(reply)
        debug("disconnect from {0} on port {1}".format(*self.client_address))
        self.STREAMING = False
        time.sleep(.1)
        self.request.close()
    
    def streamScreen(self):
        while self.STREAMING:
            self.a = screencap.stream()
            if self.a:
                reply = '{{"screen": "{0}" }}'.format(base64.b64encode(self.a))
                try:
                    self.request.send(reply)
                except SocketServer.socket.error:
                    pass
        thread.exit()
        
    def handleType(self, decode):
        debug("command from {0}:".format(self.client_address[0]))
        debug(decode)
        type = decode['type']
        '''set options'''
        if type == "SET_OPTION":
            if decode['option'] == "streaming":
                if decode['value'] == "begin":
                    self.STREAMING = True
                    stream = thread.start_new_thread(self.streamScreen, ())
                else:
                    self.STREAMING = False
                    
        '''key press'''
        if type == "EV_KEY":
            if decode['key'] == "disconnect":
                self.RUNNING = False
            else:
                try:
                    inputKey = keys.keyList[str(decode['key'])]
                    inputState = int(decode['state'])
                    doKey(inputKey, inputState)
                except KeyError:
                    debug("unknown key: {0}".format(decode['key']))
                    
        '''mouse move'''
        if type == "EV_REL":
            pass
            
        '''joystick/wheel'''
        if type == "EV_ABS":
            value = eval(decode['value'])
            setAxis(value)
            
        '''run command'''
        if type == "runCommand":
            if int(decode['state']) == 0:
                try:
                    for command in decode['key'].split(';'):
                        debug(pipe_command(command.split(' ')))
                except OSError:
                    print "invalid command:" + decode['key']



class SimpleServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    # Ctrl-C will cleanly kill all spawned threads
    daemon_threads = True
    daemon = True
    # much faster rebinding
    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass):
        #create new UInput per player connected
        try:
            ui = UInput(cap, name="STCKServer{}".format(server_address))
        except evdev.uinput.UInputError:
            print("This script must be run as sudo!")
            sys.exit(0)
        SocketServer.TCPServer.__init__(self, server_address, RequestHandlerClass)
        



if __name__ == "__main__":

    #set signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTSTP, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    
    startPort = PORT
    serverList = []
    while PORT - startPort < 10:
        
        try:
            serverList.append(SimpleServer((HOST, PORT), SingleTCPHandler))
            #broadcastServer = thread.start_new_thread(broadcast.server, (args,))
            broadcastServer = threading.Thread( name = 'broadcastServer', 
                                                target = broadcast.server, 
                                                args = (args,))
            broadcastServer.setDaemon(True)
            broadcastServer.start()
            break
        except SocketServer.socket.error:
            PORT +=1
            args.port += 1
            debug('Address already in use, trying port {}'.format(PORT))
    if PORT - startPort >= 10:
        print "Port Range {start}-{end} in use.".format(start = startPort, end = PORT)
        print "Try a different starting port."
        sys.exit(0)
    # terminate with Ctrl-C
    try:
        serverList[0].serve_forever()
    except KeyboardInterrupt:
        sys.exit(0)
