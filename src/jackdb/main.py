"""Public JackDB class with optional API setup."""
from jackdb.core import JackDB as CoreJackDB
from jackdb.api import serve_routes
from jackdb.exceptions import JdbException


class JackDB(CoreJackDB):
    """An embedded database that can also expose an API when named."""

    def __init__(self, replay_path: str = "", auto_commit: bool = True,
                 commit_size: int = 1, db_name: None | str = None):
        super().__init__(replay_path, auto_commit, commit_size, db_name)
        if self.db_name:
            self.serve()

    def serve(self):
        """
        Build and attach the API app for this database.
        """
        if self.db_name is None:
            raise JdbException("Database name must be set before serving API", 6)
        self.api = serve_routes(self.db_name, self)
