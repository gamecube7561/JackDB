"""Module containing models to be used for API operations"""
from pydantic import BaseModel


class PutModel(BaseModel):
    """
    PUT body with a required string or JSON object value.
    Objects may contain any nested JSON values, lists, numbers and booleans.

    Nulls are not supported by this HTTP endpoint.
    """
    value: str | int | float | dict | list | bool


class SetModel(BaseModel):
    """
    PUT body with a required string or JSON object value.
    Field field is a required string.
    Value field may contain any nested JSON values, lists, numbers and booleans.

    Nulls are not supported by this HTTP endpoint.
    """
    field: str
    value: str | int | float | dict | list | bool


class DeleteResponse(BaseModel):
    """
    DELETE Response body.

    Nulls are not supported by this HTTP endpoint.
    """
    message: str
    id: int | str
