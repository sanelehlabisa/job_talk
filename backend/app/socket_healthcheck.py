"""Probe production readiness over the private Nginx/Uvicorn Unix socket."""
import http.client
import os
import socket


def main():
    connection = http.client.HTTPConnection("localhost", timeout=3)
    connection.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    connection.sock.settimeout(3)
    try:
        connection.sock.connect("/run/jobtalk/api.sock")
        connection.request("GET", "/api/ready", headers={"Host": os.environ["APP_DOMAIN"]})
        if connection.getresponse().status != 200:
            raise SystemExit("Backend is not ready")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
