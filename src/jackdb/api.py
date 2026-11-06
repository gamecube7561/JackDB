"""Module that builds the API for JackDB"""
from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder

from jackdb.core import JackDB
from jackdb.api_models import PutModel, SetModel, DeleteResponse
from jackdb.exceptions import JdbException


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

    @app.put(path_prefix + "/set/{db_key}")
    def set_item(db_key: str, db_value: SetModel):
        encoded_item = jsonable_encoder(db_value)
        op = {
            'op': 'set',
            'k': db_key,
            'f': encoded_item['field'],
            'v': encoded_item['value']
        }
        try:
            result = db.do_operation(op)
            db.commit()
        except JdbException as exc:
            raise HTTPException(status_code=409, detail="Error occurred during operation.") from exc
        return result

    @app.delete(path_prefix + "/del/{db_key}")
    def del_item(db_key: str):
        op = {
            'op': 'del',
            'k': db_key
        }
        try:
            result = db.do_operation(op)
            db.commit()
        except JdbException as exc:
            raise HTTPException(status_code=409, detail="Error occurred during operation.") from exc
        return DeleteResponse(message="Item successfully deleted.", id=db_key)

    return app
