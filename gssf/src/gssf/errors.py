from enum import Enum


# These are the canonical errors for client use - wherever possible, the most
# applicable of these should be returned. They indicate where the fault is
# likely to lie.
class Error(Enum):
    SUCCESS, E_UNKNOWN, E_CLIENT, E_SERVER, E_MODEL, IN_PROGRESS, E_CANCELLED = range(7)


# A full error message (as returned via WAMP) has an id, corresponding textual
# code and the message itself
def makeError(ref, message):
    id = ref.value if isinstance(ref, Error) else Error[ref].value
    code = ref.name if isinstance(ref, Error) else Error[ref].name

    return {'id': id, 'code': code, 'message': message}


# This is the default, catch-all error - E_UNKNOWN
class GoSmartError(Exception):
    id = Error["E_UNKNOWN"]
    code = "E_UNKNOWN"


# If we have reason to believe the wrapped error is the client's responsibility
class GoSmartClientError(GoSmartError):
    id = Error["E_CLIENT"]
    code = "E_CLIENT"


# If we think this is a problem on this side of the fence
class GoSmartServerError(GoSmartError):
    id = Error["E_SERVER"]
    code = "E_SERVER"


# If we can pinpoint this as a problem with the numerical model (however, we err
# on the side of caution and attribute to server if not sure - perhaps this
# should change depending on how that feedback is used)
class GoSmartModelError(GoSmartError):
    id = Error["E_MODEL"]
    code = "E_MODEL"

exceptions = dict((e.code, e) for e in [
    GoSmartError,
    GoSmartClientError,
    GoSmartServerError,
    GoSmartModelError
])
