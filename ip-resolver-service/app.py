#!/usr/bin/env python3
"""Standalone Flask service that returns the client's public IP as JSON.

Returns: {"client_ip": "x.x.x.x"}

Install & run:
    pip install flask
    flask --app app run --host 0.0.0.0 --port 5000
"""

from flask import Flask, request, jsonify

app = Flask(__name__)


@app.route("/")
def client_ip():
    # Prefer X-Forwarded-For when behind a reverse proxy
    ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    if not ip:
        ip = request.remote_addr
    return jsonify(client_ip=ip)
