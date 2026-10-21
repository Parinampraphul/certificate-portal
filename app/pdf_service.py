"""Resolves the certificate generator dynamically so a renamed function can never cause ImportError."""
import importlib
import inspect

_CANDIDATES = (
    "generate_certificate",
    "generate_certificate_pdf",
    "create_certificate",
    "generate_pdf",
    "build_pdf",
)
_cached = None


def _resolve():
    global _cached
    if _cached is not None:
        return _cached
    module = importlib.import_module("app.certificate")
    for name in _CANDIDATES:
        fn = getattr(module, name, None)
        if callable(fn):
            _cached = fn
            return fn
    for name in dir(module):  # last resort: first public function defined in the module
        fn = getattr(module, name, None)
        if (not name.startswith("_") and inspect.isfunction(fn)
                and fn.__module__ == module.__name__):
            _cached = fn
            return fn
    raise RuntimeError("No certificate generator function found in app/certificate.py")


def render_certificate_pdf(*, name: str, event, participant) -> bytes:
    fn = _resolve()
    result = fn(
        name=name,
        event_name=event.name,
        cert_no=participant.cert_no,
        issue_date=event.issue_date,
        event_date=event.event_date,
        event_format=event.event_format or "",
        location=event.location or "",
    )
    return result if isinstance(result, (bytes, bytearray)) else result.getvalue()
