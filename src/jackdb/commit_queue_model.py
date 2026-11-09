"""Model for commit queue objects"""

class CommitQueueItem:

    def __init__(self, handler, args):
        self.handler = handler
        self.args = args