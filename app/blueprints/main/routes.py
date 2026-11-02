from flask import current_app, jsonify, render_template, send_from_directory

from . import main_bp


@main_bp.get("/")
def index():
    return render_template("main/home.html", title="책마루")


@main_bp.get("/students")
def student_access():
    return render_template("auth/invite.html", title="초대코드로 가입")


@main_bp.get("/health")
def health():
    return jsonify(status="ok", service="bookmaru", phase="PHASE 1")


@main_bp.get("/manus-routes.json")
def route_manifest():
    return send_from_directory(current_app.config["PROJECT_ROOT"] + "/public", "manus-routes.json", mimetype="application/json")


@main_bp.get("/covers/<path:filename>")
def cover(filename):
    return send_from_directory(current_app.instance_path + "/covers", filename)
