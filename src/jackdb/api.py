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

    path_prefix = f"/{db_name}"

    @app.get(path_prefix + "/size")
    def get_size():
        return len(db)

    @app.get(path_prefix + "/get/{db_key}")
    def get_item(db_key: str):
        return db[db_key]

    return app
