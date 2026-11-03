"""Module that builds the API for JackDB"""
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder

from jackdb.core import JackDB
from jackdb.api_models import PutModel


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
        op = {
            'op': 'get',
            'k': db_key
        }
        return db.do_operation(op)

    @app.put(path_prefix + "/put/{db_key}")
    def put_item(db_key: str, db_value: PutModel):
        encoded_item = jsonable_encoder(db_value)
        op = {
            'op': 'put',
            'k': db_key,
            'v': encoded_item['value']
        }
        result = db.do_operation(op)
        db.commit()
        return result

    return app
