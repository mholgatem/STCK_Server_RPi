from threading import Thread
import select
import socket
import time
import AESCipher

        
class server(Thread):
    '''
    BCAST_IP = "255.255.255.255"
    BCAST_PORT = 55535
    BUF_SIZE = 1024
    SECRET_KEY = "*4kap),dci30dm?"
    '''
    
    CURRENT_PORT = 2000
    thread_list = []

    def __init__(self, args):
        
        self.args = args
        self.BCAST_IP = args.bcastip
        self.BCAST_PORT = args.bcastport
        self.CURRENT_PORT = min(args.port, 65536)
        self.SECRET_KEY = str(args.key)
        self.BUF_SIZE = 1024
        self.SALT = args.salt #DO NOT CHANGE WITHOUT ALTERING CLIENT CODE AS WELL!
        
        self.host = self.get_host()
        address = (self.BCAST_IP, self.BCAST_PORT)
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        server_socket.bind(address)
        server_socket.setblocking(0)
        server_id = ''.join([self.SECRET_KEY, self.host,'{',str(self.CURRENT_PORT),'}'])
        
        self.debug("Listening for invitations on: {0} port: {1}".format(args.bcastip, args.bcastport))

        while True:
            result = select.select([server_socket],[],[])
            msg = result[0][0].recv(self.BUF_SIZE)
            aes = AESCipher.AESCipher(self.SECRET_KEY, self.SALT)
            msg = aes.decrypt(msg)
            self.debug("broadcast received: {0}".format(msg))
    
            if ((self.SECRET_KEY in msg) and msg != server_id):
                inviteAddress = (msg.replace(self.SECRET_KEY, ''), self.BCAST_PORT)


                server_id = '{' + ', '.join([
                                '"response": "{0}"'.format(self.SECRET_KEY),
                                '"host_name": "{0}"'.format(self.host),
                                '"server_port": {0}'.format(self.CURRENT_PORT),
                                '"disable_encrypt": "{0}"'.format(self.args.disable_encryption),
                                '"packet_size": {0}'.format(self.args.packet_size)
                                ]) + '}'

                encrypt_id = aes.encrypt(server_id)
                self.debug("Invitation authenticated. sending response to: {0}".format(inviteAddress[0]))
                server_socket.sendto(encrypt_id, inviteAddress)
    
    def debug(self, debugMessage):
        if self.args.debug:
            print '-----------------------'
            print debugMessage
            
        
        
    def get_host(self):
        host = socket.gethostname()
        if not '127' in host:
            return host
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8",0))
        host = (s.getsockname()[0])
        s.close()
        return host