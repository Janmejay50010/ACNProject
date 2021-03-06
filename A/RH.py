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

        #print("My Port=> ", self.port, "Parent's Port=> ", self.getParentAddr())
        add = ' My Parent is {}'.format(self.Parent) if self.Parent else ' I am root'
        print("Resolution Handler is online now," + add)

        self.updateYourInfo()

    def updateYourInfo(self):
        #check if file exists

        my_dict = {self.Name: self.port}
        with open(RouterMetadataPath, "r") as f:
            data = json.load(f)
            data.update(my_dict)
        
        with open(RouterMetadataPath, "w") as f:
            json.dump(data, f, indent=4)

    def UpdateYourTable(self, ClientName, filename, hop, ClientPort, nexthop = None):
        flag = False
        with open(MyTablePath, "r") as f:
            data = json.load(f)
            KeyName = ClientName + delimiter + filename
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
            print("Error while getting parent RH {} port is {}".format(self.Parent, e))
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
        _, ClientName, filename, ClientPort = message.split(delimiter)
        hop = 1
        print("Received Register request from client for file {}".format(filename))

        updated = self.UpdateYourTable(ClientName, filename, hop, ClientPort, None)

        if updated and self.Parent is not None:
            try:
                #print("Sending registration to parent {} for file {}".format(self.Parent, filename))
                self.RegisterToParent(ClientName, filename, hop+1, ClientPort, self.Name)
            except Exception as e:
                print("Error while sending Register request from Client for file {} is {}".format(ClientName+delimiter+filename, e))

    def RegisterToParent(self, ClientName, filename, hop, ClientPort, nexthop):
        try:
            print("Sending Register request to Parent {} for file {}".format(self.Parent, ClientName+delimiter+filename))
            ParentPort = self.getParentAddr()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(('0.0.0.0', ParentPort))
            message = "RegisterFromRouter" + delimiter + str(ClientName) + delimiter + filename + delimiter + str(hop) + delimiter + ClientPort + delimiter + nexthop
            s.sendall(message.encode('utf-8'))
        except Exception as e:
            print("Error while sending Register request to Parent for file {} is {}".format(ClientName+delimiter+filename, e))
        
        s.close()
    
    def RegisterFromRouter(self, connection, addr, message):
        _, ClientName, filename, hop, ClientPort, nexthop = message.split(delimiter)
        #Important to convert to integer first
        hop = int(hop)
        
        print("Received Register request from RH for file {}".format(filename))
        
        updated = self.UpdateYourTable(ClientName, filename, hop, ClientPort, nexthop)

        if updated and self.Parent is not None:
            try:
                self.RegisterToParent(ClientName, filename, hop+1, ClientPort, self.Name)
            except Exception as e:
                print("Error while Processing Register request from RH for file {} is {}".format(ClientName+delimiter+filename, e))
    
    def FindFromClient(self, connection, addr, message):
        try:
            _, OwnerName, filename, ClientPort = message.split(delimiter)
            #OwnerKey = self.getOwnerKey(filename)
            #print("Received Find request from Client {} for file {}".format(ClientPort, filename))
            print("Received Find request from Client for file {}".format(filename))

            with open(MyTablePath, "r") as f:
                data = json.load(f)
                KeyName = OwnerName + delimiter + filename
                if KeyName not in data:
                    if self.Parent is None:
                        print("File does not exist")
                    else:
                        self.FindToParent(OwnerName, filename, ClientPort)
                else:
                    destinationPort = int(data[KeyName]['ClientPort'])
                    self.FindToClient(OwnerName, filename, ClientPort, destinationPort)
        
        except Exception as e:
            print("Error while processing Find request from client for file {} is {}".format(filename, e))

    def FindToParent(self, OwnerName, filename, ClientPort):
        print("Sending Find request to parent {} for file {}".format(self.Parent, filename))
        try:
            ParentPort = self.getParentAddr()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(('0.0.0.0', ParentPort))
            message = "FindFromRouter" + delimiter + str(OwnerName) + delimiter + filename + delimiter + ClientPort
            s.sendall(message.encode('utf-8'))

        except Exception as e:
            print("Error while sending find to parent the file {} is {}".format(filename, e))
        
        sleep(.5)
        print("Sending File {} to Child Node".format(filename))

    def FindFromRouter(self, connection, addr, message):
        _, OwnerName, filename, ClientPort = message.split(delimiter)
        print("Received Find request from RH for file {}".format(filename))
        
        with open(MyTablePath, "r") as f:
            data = json.load(f)
            KeyName = OwnerName + delimiter + filename
            if KeyName not in data:
                if self.Parent is None:
                    print("File does not exist")
                else:
                    self.FindToParent(OwnerName, filename, ClientPort)
            else:
                destinationPort = data[KeyName]['ClientPort']
                self.FindToClient(OwnerName, filename, ClientPort, destinationPort)

    def FindToClient(self, OwnerName, filename, ClientPort, destinationPort):
        print("Sending find to client {} for file {}".format(destinationPort, filename))
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(('0.0.0.0', int(destinationPort)))
            message = "FindFromRouter" + delimiter + str(OwnerName) + delimiter + filename + delimiter + ClientPort
            s.sendall(message.encode('utf-8'))
        
        except Exception as e:
            print("Error while sending find to Client for file {} is {}".format(OwnerName + delimiter + filename, e))

        sleep(.5)
        print("Sending File {} to Child Node".format(filename))

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