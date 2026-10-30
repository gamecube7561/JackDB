"""Module that builds the API for JackDB"""
from fastapi import FastAPI
from jackdb.core import JackDB


def serve_routes(db_name: str, db: JackDB) -> FastAPI:
    """
    Create the API routes for JackDB
    :param db_name:
    :param db:
    :return:
    """
    app = FastAPI()

    @app.get(f"/{db_name}/size")
    def get_size():
        return len(db)

    return app
