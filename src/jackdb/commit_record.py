"""Model for commit queue objects"""


class CommitQueueItem:
    """
    Class to be used for the database commit records
    """

    def __init__(self, handler, args, record):
        self.handler = handler
        self.args = args
        self.record = record
        self.error = None
        self.result = None

    def set_error(self, error):
        """
        Set error for item
        :param error:
        :return:
        """
        self.error = error

    def set_result(self, result):
        """
        Set result for item
        :param result:
        :return:
        """
        self.result  = result
