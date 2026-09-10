import json
import socket
import threading


class NodeServer:
    def __init__(self, node_id, state, port=8000):
        self.node_id = node_id
        self.state = state
        self.port = port
        self._sock = None
        
        self.final_sync_handler = None
        self.status_provider = lambda: self.state.snapshot()

    def start(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("0.0.0.0", self.port))
        self._sock.listen(32)
        threading.Thread(target=self._accept_loop, daemon=True).start()

    def _accept_loop(self):
        while True:
            connect, _addr = self._sock.accept()
            threading.Thread(target=self._handle_connect, args=(connect,), daemon=True).start()

    def _handle_connect(self, connect):
        try:
            from . import protocol

            msg = protocol.read_message(connect)
            if msg is None:
                return
            self._dispatch(msg, connect)
        except Exception:
            pass
        finally:
            connect.close()

    def _dispatch(self, msg, conn):
        msg_type = msg.get("type")

        if msg_type == "SYNC":
            self.state.receive(
                sender_id=msg["sender_id"],
                message_id=msg.get("message_id"),
                sender_lamport=msg["lamport"],
                sender_vector=msg["vector"],
                remote_calendar=msg["calendar"],
            )

        elif msg_type == "STATUS":
            reply = dict(self.status_provider())
            reply["type"] = "STATUS_RESPONSE"
            conn.sendall((json.dumps(reply) + "\n").encode("utf-8"))

        elif msg_type == "FINAL_SYNC":
            if self.final_sync_handler:
                self.final_sync_handler()
            conn.sendall((json.dumps({"type": "FINAL_SYNC_ACK"}) + "\n").encode("utf-8"))
