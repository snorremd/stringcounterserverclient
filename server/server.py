'''
Created on Apr 12, 2013

@author: snorre
'''

import socket
import asynchat
import asyncore

import string
import random
from pickle import PickleError
from datetime import datetime

from easylogging.configLogger import getLoggerForStdOut

from tasks.taskOrganizer import TaskOrganizer
from tasks.errors import NoTasksError
from messaging.message import *

'''AuthenticationMessage, ErrorMessage, \
    TaskMessage, RequestMessage, ResultMessage, AuthErrorMessage
'''
from messaging.pickling import serialize_message, deserialize_message


class Server(asyncore.dispatcher):

    '''Receive connections and establish handlers for each client
    '''

    def __init__(self, address, timeoutSeconds, tasks, batchSize):
        '''Initialize Server
        '''
        asyncore.dispatcher.__init__(self)

        self.logger = getLoggerForStdOut("Server")

        self.programId = "StringCounter"
        self.timeoutSeconds = timeoutSeconds
        self.batchSize = batchSize
        self.clientSockets = {}

        self.taskOrganizer = TaskOrganizer(timeoutSeconds, tasks)

        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)  # IPv4, TCP
        self.bind(address)
        self.address = self.socket.getsockname()
        self.logger.debug("Created server socket at " + str(self.address))
        self.listen(100)
        return

    def handle_accept(self):
        '''Handle incoming calls from client
        '''
        clientInfo = self.accept()  # Should return socket and address
        '''
        self.logger.debug("Client with address %s connected to server socket"
                          % str(clientInfo[1]))
        '''

        client = ClientHandler(clientInfo[0], clientInfo[1], self)
        self.clientSockets[client.clientId] = client  # Add with unique id

    def handle_close(self):
        '''Close server socket
        '''
        self.logger.debug("Server closing server socket")
        self.close()

    def remove_client(self, clientId):
        '''Removed the identified client from the list
        '''
        del self.clientSockets[clientId]


class ClientHandler(asynchat.async_chat):

    '''Handle communication with single client socket
    '''
    # Use default buffer size of 4096 bytes (4kb)
    def __init__(self, clientSock, clientAddress, serverSocket):
        self.logger = getLoggerForStdOut("ClientHandler")
        asynchat.async_chat.__init__(self, sock=clientSock)
        self.serverSocket = serverSocket

        self.clientId = clientAddress
        self.programId = serverSocket.programId
        self.batchSize = serverSocket.batchSize

        self.taskOrganizer = serverSocket.taskOrganizer
        self.currentTasks = {}

        self.authorized = False

        self.receivedData = []  # String data from client

        self.set_terminator('</' + self.programId + '>')  # Break on </xml> or linesep
        return

    def collect_incoming_data(self, data):
        self.receivedData.append(data)

    def found_terminator(self):
        '''Found the terminator in the input from the client
        '''
        self.process_message()

    def process_message(self):
        '''Received all command input from client. Send back data
        '''
        stringInput = ''.join(self.receivedData)  # Complete data from client
        # self.logger.debug('Process command: %s', command)
        try:
            message = deserialize_message(stringInput)
        except PickleError:
            errorMessage = ErrorMessage("Could not deserialize message",
                                        "Deserialization error")
            self.send_message(errorMessage)
        else:
            if isinstance(message, RequestMessage):
                self.send_client_tasks()
            elif isinstance(message, ResultMessage):
                self.handle_client_results(message)
            elif isinstance(message, AuthenticationMessage):
                self.authorize_client(message)
            elif isinstance(message, DisconnectMessage):
                self.disconnect_client(message)
        self.receivedData = []

    def send_message(self, message):
        '''Sends a message object to a client
        '''
        pickledMessage = serialize_message(message)
        self.push(pickledMessage + self.get_terminator())

    def authorize_client(self, messageObj):
        if messageObj.authData == self.programId:
            self.authorized = True
            authMessage = AuthenticationMessage("Authentification suceeded",
                                      "Authentification data was correct")
            self.send_message(authMessage)

        else:
            errorMessage = AuthErrorMessage("Authentification failed",
                                            messageObj.authData,
                                            "Auth data was not correct")
            self.send_message(errorMessage)
            self.serverSocket.remove_client(self.clientId)
            self.close_when_done()

    def disconnect_client(self, message):
        self.serverSocket.remove_client(self.clientId)
        self.close_when_done()
        self.logger.debug("Client disconnected (id: " + str(self.clientId) + \
                          " ), because " + message.disconnectInfo)

    def send_client_tasks(self):
        try:
            tasks = self.taskOrganizer.get_tasks(self.batchSize)
        except NoTasksError:
            errorMessage = NoTasksMessage("No tasks error",
                                        "Currently no tasks to execute")
            self.send_message(errorMessage)
        else:
            taskMessage = TaskMessage("Task:", tasks)
            self.send_message(taskMessage)

    def handle_client_results(self, resultMessage):
        results = resultMessage.results
        if self.check_tasks_authenticity(results.keys()):
            self.taskOrganizer.finish_tasks(results)
        else:
            message = TaskAuthenticationError("Task authentication error",
                                              results.keys())
            self.send_message(message)
        self.currentTasks = {}
        self.logger.debug("Received and handled " + str(len(results)) + \
                          " results from client")
        self.logger.debug(str(len(self.taskOrganizer.pendingTasks)) + \
                          " tasks remaining")

    def check_tasks_authenticity(self, taskIds):
        '''Check if results from client match current task ids

        Args:
            taskIds (list): a list of keys from client results

        Returns:
            boolean (true/false) if taskIds match with activeTasks
        '''
        if all(taskId in self.currentTasks for taskId in taskIds):
            return True
        else:
            return False