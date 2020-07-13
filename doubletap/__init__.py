import logging

handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("[%(name)s] %(levelname)s - %(message)s"))

log = logging.getLogger("doubletap")
log.setLevel(logging.DEBUG)
log.addHandler(handler)
