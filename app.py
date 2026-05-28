from flask import Flask, flash, redirect, render_template, request, session, url_for

import config
import database as db

app = Flask(__name__)
app.secret_key = config.FLASK_SECRET_KEY


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/submit", methods=["POST"])
def submit():
    user_id     = request.form["user_id"].strip()
    origin      = request.form["origin"].strip().upper()
    destination = request.form["destination"].strip().upper()
    date        = request.form["date"]
    contact     = request.form["contact"].strip()
    seat        = request.form.get("seat", "economy")
    adults      = int(request.form.get("adults", 1))

    try:
        threshold = float(request.form["threshold"])
    except ValueError:
        flash("Threshold must be a number.", "error")
        return redirect(url_for("index"))

    if not all([user_id, origin, destination, date, contact]):
        flash("All fields are required.", "error")
        return redirect(url_for("index"))

    db.add_monitoring_request(
        user_id=user_id,
        origin=origin,
        destination=destination,
        travel_date=date,
        threshold=threshold,
        contact=contact,
        seat=seat,
        adults=adults,
    )

    session["user_id"] = user_id
    flash(f"Now monitoring {origin} → {destination} on {date} below ${threshold:.2f}.", "success")
    return redirect(url_for("routes"))


@app.route("/routes")
def routes():
    user_id = session.get("user_id", "")
    requests = []
    if user_id:
        requests = db.get_user_monitoring_requests(user_id)
    return render_template("routes.html", user_id=user_id, requests=requests)


@app.route("/lookup", methods=["POST"])
def lookup():
    user_id = request.form["user_id"].strip()
    session["user_id"] = user_id
    return redirect(url_for("routes"))


@app.route("/cancel", methods=["POST"])
def cancel():
    user_id    = request.form["user_id"]
    request_id = request.form["request_id"]
    db.deactivate_monitoring_request(user_id, request_id)
    flash("Monitoring request cancelled.", "success")
    return redirect(url_for("routes"))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    db.init_db()
    app.run(host="0.0.0.0", port=config.FLASK_PORT, debug=False)
