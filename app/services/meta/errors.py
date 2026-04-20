class MetaError(Exception):
    def __init__(self, message: str, code: int | None = None, raw: dict | None = None):
        super().__init__(message)
        self.code = code
        self.raw = raw or {}


class TokenExpired(MetaError):
    ...


class RateLimited(MetaError):
    def __init__(self, *a, retry_after: int = 60, **kw):
        super().__init__(*a, **kw)
        self.retry_after = retry_after


class PostingIDRevoked(MetaError):
    ...


class MediaRejected(MetaError):
    ...


class MetaTimeout(MetaError):
    ...


class TransientMetaError(MetaError):
    ...


_PERM = {190: TokenExpired, 1366046: MediaRejected}
_RATE = {4, 17, 32, 613}


def classify_error(resp: dict, retry_after: int = 60, is_posting_id: bool = False) -> MetaError:
    err = resp.get("error", {})
    code = err.get("code")
    msg = err.get("message", "Meta error")
    if code in _PERM:
        return _PERM[code](msg, code=code, raw=err)
    if code in _RATE:
        return RateLimited(msg, code=code, raw=err, retry_after=retry_after)
    if code == 100 and is_posting_id:
        return PostingIDRevoked(msg, code=code, raw=err)
    return TransientMetaError(msg, code=code, raw=err)
