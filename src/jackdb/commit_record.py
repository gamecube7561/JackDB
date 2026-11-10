"""Model for commit queue objects"""


class CommitQueueItem:
    """
    Class to be used for the database commit records
    """

    def __init__(self, handler, args, record):
        self._handler = handler
        self._args = args
        self._record = record
        self.error = None
        self.result = None

    @property
    def handler(self) -> str:
        """
        Returns the handler property.
        :return:
        """
        return self._handler

    @property
    def args(self):
        """
        Returns the args property.
        :return:
        """
        return self._args

    @property
    def record(self):
        """
        Returns the record property.
        :return:
        """
        return self._record

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
