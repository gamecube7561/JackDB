"""Module containing specification for the operations."""
from jackdb.exceptions import JdbException

OPERATION_SPECS = {
    # op: (required fields, journaled, handler)
    "put": (("k", "v"), True, "do_put"),
    "del": (("k",), True, "do_del"),
    "get": (("k",), False, "do_get"),
    "get_many": (("k",), False, "do_get_many"),
    "set": (("k", "f", "v"), True, "do_set"),
}
OPERATION_TYPES = list(OPERATION_SPECS)


def _resolve(record):
    """Validate one operation record's shape against ``OPERATION_SPECS``.

    :return: Tuple of (journaled, handler name, extracted arguments).
    :raises JdbException: On unknown ``op`` or missing required fields.
    """
    try:
        op_code = record["op"]
    except (KeyError, TypeError) as e:
        raise JdbException("Can not parse operation key.", 4) from e

    spec = OPERATION_SPECS.get(op_code)
    if spec is None:
        raise JdbException("Unsupported operation type.", 3)

    fields, journaled, handler_name = spec
    args = []
    for field_name in fields:
        try:
            args.append(record[field_name])
        except KeyError as e:
            raise JdbException("Can not parse key value", 4) from e
    return journaled, handler_name, args
