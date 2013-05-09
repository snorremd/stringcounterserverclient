from collections import deque
from errors import NoTasksError
from datetime import datetime


class TaskOrganizer(object):

    '''Receive connections and establish handlers for each client
    '''

    def __init__(self, timeoutSeconds, tasks):
        '''Initialize StringCounterServer
        '''
        self.pendingTasks = deque([])
        self.activeTasks = {}
        self.results = []
        self.timeout = timeoutSeconds

    def add_tasks(self, tasks):
        '''Add all elements of tasks to pending tasks
        '''
        self.pendingTasks.extend(tasks)

    def get_task(self):
        '''Get first remaning task if any

        Returns:
            A task id and first available task object.
            If none available, raise NoTasksError.
        '''
        task = None
        try:
            task = self.pendingTasks.popleft()
        except IndexError:
            raise NoTasksError("There are no remaning tasks in" +
                               " pendingTasks deque")
        else:  # No exceptions raised
            taskId = self.make_task_active(task)
            return taskId, task

    def make_task_active(self, task):
        '''Add a task to the active jobs dictionary

        Args:
            task (Task): The task to make active

        Returns:
            currentTime (object) of when task was created
        '''
        currentTime = datetime.now()
        self.activeTasks[currentTime] = task
        return currentTime

    def check_active_tasks(self):
        '''Check active tasks for timeouts

        For each task in active tasks, check if the
        task has timed out, and if so reinsert into
        pendingTasks deque and remove from active tasks dict.
        '''
        currentTime = datetime.now()
        for timestamp in self.activeTasks.keys():
            difference = currentTime - timestamp
            if difference.seconds > self.timeout:
                self.pendingTasks.append(self.activeTasks[timestamp])
                del self.pendingTasks[timestamp]

    def task_active(self, taskId):
        '''Check if a task is still active

        Args:
            taskId (object): the id of the task to be checked

        Returns:
            True if task still active, False if not
        '''
        if taskId in self.activeTasks:
            return True
        else:
            return False

    def finish_task(self, taskId, result):
        '''Finish task

        Args:
            taskId (object): the id of the task to finish
            result (Result): the finished result
        '''
        self.results[result]
        del self.activeTasks[taskId]
