import json
import sys
from io import TextIOWrapper
from json import JSONDecodeError


class JackDB:
    def __init__(self, replay_path: str = ""):
        self.replay_file: TextIOWrapper
        self.data_dict = {}
        self.replay_path = replay_path
        self.records = []
        self.log_length = 0

        if self.replay_path == "":
            print("No replay provided, using empty dictionary...")
            sys.exit(1)
        else:
            print(f"Replay file {replay_path} provided. Loading dictionary...")
            self.replay_file = open(self.replay_path, "a+", encoding="utf-8")
            self.load_from_file()

    def load_from_file(self):
        self.replay_file.seek(0)  # "a+" opens at EOF; replay must read from the start
        for line in self.replay_file:
            try:
                record = json.loads(line)
                self.do_operation(record)
            except JSONDecodeError:
                break

        self.log_length = len(self.records)

    def do_operation(self, operation):
        if not isinstance(operation, dict):
            record = json.loads(operation)
        else:
            record = operation

        if record["op"] == "put":
            self.records.append(record)
            key = record["k"]
            value = record["v"]
            return self.do_put(key, value)
        elif record["op"] == "del":
            self.records.append(record)
            key = record["k"]
            return self.do_del(key)
        elif record["op"] == "get":
            key = record["k"]
            return self.do_get(key)

        return None

    def flush_logs(self):
        while self.log_length < len(self.records):
            string_record = json.dumps(self.records[self.log_length])
            self.replay_file.write(string_record + '\n')
            self.log_length += 1
        self.replay_file.flush()

    def do_put(self, key, value) -> str:
        try:
            self.data_dict[key] = value
            return self.data_dict[key]
        except KeyError:
            return ""

    def do_del(self, key) -> bool:
        """

        :param key:
        :return:
        """
        try:
            del self.data_dict[key]
            return True
        except KeyError:
            return False

    def do_get(self, key) -> str:
        """
        Retrieve data from the database using it's key.
        :param key: Database key
        :type key: str
        :return: Not sure yet
        """
        try:
            return self.data_dict[key]
        except KeyError:
            return ""