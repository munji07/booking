from flask import current_app, jsonify, render_template, send_from_directory

from . import main_bp


@main_bp.get("/")
def index():
    return render_template("main/home.html", title="책마루")


@main_bp.get("/health")
def health():
    return jsonify(status="ok", service="bookmaru", phase="PHASE 1")


@main_bp.get("/manus-routes.json")
def route_manifest():
    return send_from_directory(current_app.config["PROJECT_ROOT"] + "/public", "manus-routes.json", mimetype="application/json")
