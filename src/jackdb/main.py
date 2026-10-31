"""Public JackDB class with optional API setup."""
from jackdb.core import JackDB as CoreJackDB
from jackdb.api import serve_routes


class JackDB(CoreJackDB):
    """An embedded database that can also expose an API when named."""

    def __init__(self, replay_path: str = "", auto_commit: bool = True,
                 commit_size: int = 10, db_name: str = ""):
        super().__init__(replay_path, auto_commit, commit_size, db_name)
        if self.db_name:
            self.serve()

    def serve(self):
        """
        Build and attach the API app for this database.
        """
        self.api = serve_routes(self.db_name, self)
