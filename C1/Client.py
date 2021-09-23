import os, json, sys
import re, random
import threading, socket
from threading import Lock
from time import sleep

ClientMetadataPath = "./ClientMetadata.json"
RouterMetadataPath = '../RouterMetadata.json'
FileMetadataPath = '../FileMetadata.json'
delimiter = '#'

class Client():
    Name = None
    PublicKey = None
    PrivateKey = None
    RouterPort = None
    RouterName = None
    port = None
    sock = None

    def __init__(self, name, routerName):
        self.Name = name
        self.RouterName = routerName
        self.sock = socket.socket()
        self.sock.bind(('', 0))
        self.port = str(self.sock.getsockname()[1])

        self.RouterPort = self.getRouterPort()
        
        print("My port=> ",self.port, "MyRouterPort=> ", self.RouterPort)
        self.updateYourInfo()
    
    def getRouterPort(self):
        try:
            with open(RouterMetadataPath, "r") as f:
                data = json.load(f)
                return int(data[self.RouterName])
        except Exception as e:
            print("Error while getting port for Router {} is {}".format(self.RouterName, e))
            sys.exit()

    def PrintAllCommands(self):
        print("Commands are Register Filename, Find Filename")
    
    def getOwnerKey(self, filename):
        with open(FileMetadataPath) as f:
            data = json.load(f)
        
        return data[filename]

    def GenerateKeyPairs(self):
        return self.Name, "Hahah"

    def updateYourInfo(self):
        #check if file exists
        with open(ClientMetadataPath, "r") as f:
            data = json.load(f)
            if self.Name in data:
                self.PublicKey = data[self.Name]["PublickKey"]
                self.PrivateKey = data[self.Name]["PrivateKey"]
            else:
                self.PublicKey, self.PrivateKey = self.GenerateKeyPairs()
                data[self.Name] = {}
                data[self.Name]["PublickKey"] = self.PublicKey
                data[self.Name]["PrivateKey"] = self.PrivateKey
                
        data[self.Name]["Port"] = self.port
        data[self.Name]["RouterPort"] = self.RouterPort   
        with open (ClientMetadataPath, "w") as fp:
            json.dump(data, fp, indent = 4)
            
    def Listen(self):
        #print("Starting to listen ")
        self.sock.listen(5)
        while True:
            connection, addr = self.sock.accept()
            #print(connection, addr)
            ServeThread = threading.Thread(target = self.serve, args = (connection, addr))
            ServeThread.start()

    def serve(self, connection, addr):
        message = connection.recv(1024)
        message = message.decode('utf-8')
        commandType = message.split(delimiter)[0]

        #Make client sleep here
        if commandType == "FindFromRouter":
            self.FindFromRouter(connection, addr, message)
        
        elif commandType == "ReceiveFile":
            self.ReceiveFile(connection, addr, message)

    def RegisterToRouter(self, filename):
        #check if file exists or not
        #print("Registering {} to router {}".format(filename, self.RouterName))
        with open(FileMetadataPath) as f:
            data = json.load(f)
            my_dict = {filename: self.PublicKey}
            data.update(my_dict)
        
        with open (FileMetadataPath, "w") as fp:
            json.dump(data, fp, indent = 4)
        
        try:
            self.RouterPort = self.getRouterPort()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(('0.0.0.0', self.RouterPort))
            message = "RegisterFromClient" + delimiter + self.PublicKey + delimiter + filename + delimiter + self.port
            s.sendall(message.encode('utf-8'))

        except Exception as e:
            print("Error while registering file {} to Router {} is {}".format(filename, self.RouterName, e))

        s.close()
        
    def FindToRouter(self, filename):
        #check if file exists or not

        OwnerKey = self.getOwnerKey(filename)
        try:
            self.RouterPort = self.getRouterPort()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(('0.0.0.0', self.RouterPort))

            message = "FindFromClient" + delimiter + OwnerKey + delimiter + filename + delimiter + self.port
            s.sendall(message.encode('utf-8'))

        except Exception as e:
            print("Error while Sending Find to Router {} for file {} is ".format(self.RouterName, e))

        s.close()

    def FindFromRouter(self, connection, addr, message):
        _, Publickey, filename, DestinationPort = message.split(delimiter)

        #check if file exists
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(('0.0.0.0', int(DestinationPort)))

            message = "SendFile" + delimiter + filename
            s.sendall(message.encode('utf-8'))
            sleep(1)
            
            with open('./' + filename, 'rb') as fp:
                bytes_to_read = 1024
                file_data = fp.read(bytes_to_read)
                while file_data:
                    s.sendall(file_data)
                    #offset += bytes_to_read
                    file_data = fp.read(bytes_to_read)

        except Exception as e:
            print('Error while sending file {} is {}'.format(filename, e))
        
        s.close()
        
    def ReceiveFile(self, connection, addr, message):
        try:
            _, filename = message.split(delimiter)

            with open('./' + filename, 'wb') as f:
                file_data = connection.recv(1024)
                while file_data:
                    f.write(file_data)
                    file_data = connection.recv(1024)
        
        except Exception as e:
            print('Error when receiving file {} is {}'.format(filename, e))
        
        connection.close()

def main():
    #Get Client name and Router name
    if(len(sys.argv) != 3):
        print("Correct usage is =>: ClientName RounterName")
        sys.exit()
    
    clientName = sys.argv[1]
    routerName = sys.argv[2]

    #Initialize the Client
    C = Client(clientName, routerName)

    ClientAsServerThread = threading.Thread(target = C.Listen)
    ClientAsServerThread.start()
    
    #print("Hey, main thread here\n")
    C.PrintAllCommands()
    while True:
        command = input(":")
        tokens = command.split(' ')
        if(len(tokens) != 2):
            print("Invalid Format of command")
            continue
        
        commandType = tokens[0].lower()
        filename = tokens[1]
        if commandType == "register":
            C.RegisterToRouter(filename)
        
        elif commandType == "find":
            C.FindToRouter(filename)
        
        else:
            print("Invalid command type")
            continue
        
if __name__ == '__main__':
    main()


