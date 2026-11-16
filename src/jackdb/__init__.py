"""Init file for the JackDB package"""
import logging
from jackdb.main import JackDB

VERSION = "0.3.2"

__version__ = VERSION
logging.getLogger(__name__).addHandler(logging.NullHandler())
