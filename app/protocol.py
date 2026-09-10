

import json
import socket


def send_message(host, port, message, timeout=5, retries=5, retry_delay=1.0):
    
    import time

    data = (json.dumps(message) + "\n").encode("utf-8")
    previous_error = None

    for attempt in range(retries):
        try:
            with socket.create_connection((host, port), timeout=timeout) as sock:
                sock.sendall(data)
            return
        except OSError as exc:
            previous_error = exc
            time.sleep(retry_delay)
    raise ConnectionError(
        f"could not reach {host}:{port} after {retries} attempts: {previous_error}"
    )


def send_message_and_wait(host, port, message, timeout=5):
    data = (json.dumps(message) + "\n").encode("utf-8")
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.sendall(data)
        sock.settimeout(timeout)
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = sock.recv(65536)
            if not chunk:
                break
            buf += chunk
    if not buf:
        return None
    return json.loads(buf.decode("utf-8"))


#Read newline-terminated JSON message from accepted connection.

def read_message(conn):
    
    buf = b""
    while not buf.endswith(b"\n"):
        chunk = conn.recv(65536)
        if not chunk:
            break
        buf += chunk
    if not buf:
        return None
    return json.loads(buf.decode("utf-8"))
