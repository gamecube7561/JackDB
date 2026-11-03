"""Module containing models to be used for API operations"""
from pydantic import BaseModel

class PutModel(BaseModel):
    """
    PUT body with a required string or JSON object value.

    Objects may contain any nested JSON values. Top-level arrays, numbers,
    booleans, and null are not supported by this HTTP endpoint.
    """
    value: str | dict
