import os, sqlite3, json
import re, random, sys
import threading, socket
from threading import Lock
from time import sleep

RouterMetadataPath = '../RouterMetadata.json'
MyTablePath = './MyTable.json'
FileMetadataPath = '../FileMetadata.json'
delimiter = '#'

class Router():
    Name = None
    Parent = None
    sock = None
    port = None

    def __init__(self, name, parent=None):
        self.Name = name
        self.Parent = parent
        self.sock = socket.socket()
        self.sock.bind(('', 0))
        self.port = str(self.sock.getsockname()[1])
        print("My Port=> ", self.port, "Parent's Port=> ", self.getParentAddr())

        self.updateYourInfo()

    def updateYourInfo(self):
        #check if file exists

        my_dict = {self.Name: self.port}
        with open(RouterMetadataPath, "r") as f:
            data = json.load(f)
            data.update(my_dict)
        
        with open(RouterMetadataPath, "w") as f:
            json.dump(data, f, indent=4)

    def UpdateYourTable(self, key, filename, hop, ClientPort, nexthop = None):
        flag = False
        with open(MyTablePath, "r") as f:
            data = json.load(f)
            KeyName = key + delimiter + filename
            if KeyName not in data:
                data[KeyName] = {}
                flag = True
            elif data[KeyName]['HopDistance'] > hop:
                flag = True
            
            if(flag):
                data[KeyName]['HopDistance'] = hop
                data[KeyName]['ClientPort'] = ClientPort
                data[KeyName]['nexthop'] = nexthop
                
                with open(MyTablePath, "w") as f:
                    json.dump(data, f, indent = 4)
        
        return flag

    def getOwnerKey(self, filename):
        with open(FileMetadataPath) as f:
            data = json.load(f)
        
        return data[filename]

    def getParentAddr(self):
        if self.Parent is None:
            return None
        try:
            with open(RouterMetadataPath, "r") as f:
                data = json.load(f)
                ParentPort = data[self.Parent]
        except Exception as e:
            print("Error while getting parent Router {} port is {}".format(self.Parent, e))
            sys.exit()
            
        return int(ParentPort)

    def listen(self):
        self.sock.listen()
        while(True):
            connection, addr = self.sock.accept()
            self.serve(connection, addr)
    
    def serve(self, connection, addr):
        message = connection.recv(1024)
        message = message.decode('utf-8')
        commandType = message.split(delimiter)[0]
        if commandType == "RegisterFromClient":
            #print("Received Registration from client")
            self.RegisterFromClient(connection, addr, message)

        elif commandType == "RegisterFromRouter":
            #print("Received Registration from Router")
            self.RegisterFromRouter(connection, addr, message)
        
        elif commandType == "FindFromClient":
            self.FindFromClient(connection, addr, message)
        
        elif commandType == "FindFromRouter":
            self.FindFromRouter(connection, addr, message)
    
    def RegisterFromClient(self, connection, addr, message):
        _, key, filename, ClientPort = message.split(delimiter)
        hop = 1
        print("Received Registration from client {} for file {}".format(ClientPort, filename))

        updated = self.UpdateYourTable(key, filename, hop, ClientPort, None)

        if updated and self.Parent is not None:
            try:
                print("Sending registration to parent {} for file {}".format(self.Parent, filename))
                self.RegisterToParent(key, filename, hop+1, ClientPort, self.Name)
            except Exception as e:
                print("Error while registering from Client for file {} is {}".format(key+delimiter+filename, e))

    def RegisterToParent(self, key, filename, hop, ClientPort, nexthop):
        try:
            print("Sending registration to parent {} for file {}".format(self.Parent, key+delimiter+filename))
            ParentPort = self.getParentAddr()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(('0.0.0.0', ParentPort))
            message = "RegisterFromRouter" + delimiter + str(key) + delimiter + filename + delimiter + str(hop) + delimiter + ClientPort + delimiter + nexthop
            s.sendall(message.encode('utf-8'))
        except Exception as e:
            print("Error while sending registration to parent for file {} is {}".format(key+delimiter+filename, e))
        
        s.close()
    
    def RegisterFromRouter(self, connection, addr, message):
        _, key, filename, hop, ClientPort, nexthop = message.split(delimiter)
        #Important to convert to integer first
        hop = int(hop)
        
        print("Received Registration from Router for file {}".format(filename))
        
        updated = self.UpdateYourTable(key, filename, hop, ClientPort, nexthop)

        if updated and self.Parent is not None:
            try:
                self.RegisterToParent(key, filename, hop+1, ClientPort, self.Name)
            except Exception as e:
                print("Error while registering from router {} for file {} is {}".format(nexthop, key+delimiter+filename, e))
    
    def FindFromClient(self, connection, addr, message):
        try:
            _, key, filename, ClientPort = message.split(delimiter)
            #OwnerKey = self.getOwnerKey(filename)
            print("Received Find from Client {} for file {}".format(ClientPort, filename))

            with open(MyTablePath, "r") as f:
                data = json.load(f)
                KeyName = key + delimiter + filename
                if KeyName not in data:
                    if self.Parent is None:
                        print("File does not exist")
                    else:
                        self.FindToParent(key, filename, ClientPort)
                else:
                    destinationPort = int(data[KeyName]['ClientPort'])
                    self.FindToClient(key, filename, ClientPort, destinationPort)
        
        except Exception as e:
            print("Error while processing find from client for file {} is {}".format(filename, e))

    def FindToParent(self, key, filename, ClientPort):
        print("Sending find to parent for file {}".format(filename))
        try:
            ParentPort = self.getParentAddr()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(('0.0.0.0', ParentPort))
            message = "FindFromRouter" + delimiter + str(key) + delimiter + filename + delimiter + ClientPort
            s.sendall(message.encode('utf-8'))

        except Exception as e:
            print("Error while sending find to parent the file {} is {}".format(filename, e))

    def FindFromRouter(self, connection, addr, message):
        _, key, filename, ClientPort = message.split(delimiter)
        print("Received Find from Router for file {}".format(filename))
        
        with open(MyTablePath, "r") as f:
            data = json.load(f)
            KeyName = key + delimiter + filename
            if KeyName not in data:
                if self.Parent is None:
                    print("File does not exist")
                else:
                    self.FindToParent(key, filename, ClientPort)
            else:
                destinationPort = data[KeyName]['ClientPort']
                self.FindToClient(key, filename, ClientPort, destinationPort)

    def FindToClient(self, key, filename, ClientPort, destinationPort):
        print("Sending find to client {} for file {}".format(destinationPort, filename))
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(('0.0.0.0', int(destinationPort)))
            message = "FindFromRouter" + delimiter + str(key) + delimiter + filename + delimiter + ClientPort
            s.sendall(message.encode('utf-8'))
        
        except Exception as e:
            print("Error while sending find to Client for file {} is {}".format(key + delimiter + filename, e))

        s.close()   

def main():
    #Initialize the Router
    parentRouter = None
    myName = sys.argv[1]
    if len(sys.argv) > 2:
        parentRouter = sys.argv[2]
    R = Router(myName, parentRouter)
    R.listen()
    
if __name__ == '__main__':
    main()