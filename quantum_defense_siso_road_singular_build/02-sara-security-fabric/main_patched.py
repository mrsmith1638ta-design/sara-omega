import logging
import os
from flask import Flask, jsonify, request

logger = logging.getLogger("sara-security-fabric.main_patched")

try:
    from phase3_security.service_app import route
except Exception as exc:
    raise RuntimeError("phase3_security.service_app route is required") from exc

app = Flask(__name__)


def _body():
    if not request.data:
        return {}
    return request.get_json(silent=True) or {}


@app.route("/health", methods=["GET"])
def health():
    if route is not None:
        service = os.environ.get("SARA_SECURITY_SERVICE", "security-fabric")
        status, body = route(service, "/health", {})
        return jsonify(body), status
    return jsonify({"service": "security-fabric", "status": "operational"})


@app.route("/", defaults={"path": ""}, methods=["GET", "POST"])
@app.route("/<path:path>", methods=["GET", "POST"])
def passthrough(path):
    service = os.environ.get("SARA_SECURITY_SERVICE", "security-fabric")
    status, body = route(service, "/" + path, _body())
    return jsonify(body), status


from fabric_pqc_patch import register_fabric_pqc

register_fabric_pqc(app)
