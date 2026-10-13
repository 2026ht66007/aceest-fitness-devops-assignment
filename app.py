import os
import random
import sqlite3
from datetime import date

from flask import Flask, g, jsonify, render_template_string, request


PROGRAMS = {
    "Fat Loss": [
        ("Fat Loss (FL) – 3 day", 22),
        ("Fat Loss (FL) – 5 day", 24),
    ],
    "Muscle Gain": [
        ("Muscle Gain (MG) – PPL", 35),
    ],
    "Beginner": [
        ("Beginner (BG)", 26),
    ],
}


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=os.environ.get(
            "ACEEST_DATABASE",
            os.path.join(app.instance_path, "aceest_fitness.db"),
        )
    )
    if test_config:
        app.config.update(test_config)

    db_path = app.config["DATABASE"]
    if db_path != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

    def connect_db():
        connection = sqlite3.connect(app.config["DATABASE"])
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def get_db():
        if "db" not in g:
            g.db = connect_db()
        return g.db

    @app.teardown_appcontext
    def close_db(_error=None):
        connection = g.pop("db", None)
        if connection is not None:
            connection.close()

    def initialize_db():
        connection = connect_db()
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                age INTEGER,
                height REAL,
                weight REAL,
                program TEXT,
                calories INTEGER,
                target_weight REAL,
                target_adherence INTEGER,
                membership_status TEXT NOT NULL DEFAULT 'Active',
                membership_end TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_name TEXT NOT NULL,
                week TEXT NOT NULL,
                adherence INTEGER NOT NULL,
                FOREIGN KEY (client_name) REFERENCES clients(name)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS workouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_name TEXT NOT NULL,
                date TEXT NOT NULL,
                workout_type TEXT NOT NULL,
                duration_min INTEGER NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (client_name) REFERENCES clients(name)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS exercises (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workout_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                sets INTEGER NOT NULL,
                reps INTEGER NOT NULL,
                weight REAL,
                FOREIGN KEY (workout_id) REFERENCES workouts(id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_name TEXT NOT NULL,
                date TEXT NOT NULL,
                weight REAL,
                waist REAL,
                bodyfat REAL,
                FOREIGN KEY (client_name) REFERENCES clients(name)
                    ON DELETE CASCADE
            );
            """
        )
        connection.commit()
        connection.close()

    def find_client(name):
        return get_db().execute(
            "SELECT * FROM clients WHERE name = ?", (name,)
        ).fetchone()

    def missing_client():
        return jsonify(error="Client not found."), 404

    initialize_db()

    @app.get("/")
    def home():
        return render_template_string(
            """
            <!doctype html>
            <html lang="en">
              <head><meta charset="utf-8"><title>ACEest Fitness</title></head>
              <body>
                <h1>ACEest Fitness &amp; Gym</h1>
                <p>Client, workout, progress, and membership management.</p>
                <p><a href="/health">Health check</a></p>
                <p><a href="/clients">Clients API</a></p>
              </body>
            </html>
            """
        )

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.route("/clients", methods=["GET", "POST"])
    def clients():
        db = get_db()

        if request.method == "GET":
            rows = db.execute(
                "SELECT * FROM clients ORDER BY name"
            ).fetchall()
            return jsonify([dict(row) for row in rows])

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="Send a JSON object."), 400

        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            return jsonify(error="Client name is required."), 400

        height = data.get("height")
        weight = data.get("weight")
        for field, value in (("height", height), ("weight", weight)):
            if value is not None and (
                not isinstance(value, (int, float)) or isinstance(value, bool)
            ):
                return jsonify(error=f"{field} must be a number."), 400

        program = data.get("program")
        factors = {plan: factor for plans in PROGRAMS.values()
                   for plan, factor in plans}
        if program and program not in factors:
            return jsonify(error="Choose a listed fitness program."), 400

        calories = int(weight * factors[program]) if weight and program else None
        try:
            cursor = db.execute(
                """
                INSERT INTO clients (
                    name, age, height, weight, program, calories,
                    target_weight, target_adherence,
                    membership_status, membership_end
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name.strip(),
                    data.get("age"),
                    height,
                    weight,
                    program,
                    calories,
                    data.get("target_weight"),
                    data.get("target_adherence"),
                    data.get("membership_status", "Active"),
                    data.get("membership_end", ""),
                ),
            )
            db.commit()
        except sqlite3.IntegrityError:
            return jsonify(error="A client with that name already exists."), 409

        row = db.execute(
            "SELECT * FROM clients WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return jsonify(dict(row)), 201

    @app.get("/clients/<client_name>")
    def get_client(client_name):
        row = find_client(client_name)
        if row is None:
            return missing_client()
        return jsonify(dict(row))

    @app.get("/clients/<client_name>/membership")
    def membership(client_name):
        row = find_client(client_name)
        if row is None:
            return missing_client()
        return jsonify(
            name=row["name"],
            membership_status=row["membership_status"],
            membership_end=row["membership_end"],
        )

    @app.post("/clients/<client_name>/program")
    def generate_program(client_name):
        db = get_db()
        row = find_client(client_name)
        if row is None:
            return missing_client()

        data = request.get_json(silent=True) or {}
        program_type = data.get("program_type", "Beginner")
        if program_type not in PROGRAMS:
            return jsonify(error="Choose Fat Loss, Muscle Gain, or Beginner."), 400

        program, factor = random.choice(PROGRAMS[program_type])
        calories = int(row["weight"] * factor) if row["weight"] else None
        db.execute(
            "UPDATE clients SET program = ?, calories = ? WHERE name = ?",
            (program, calories, client_name),
        )
        db.commit()
        return jsonify(program=program, calories=calories), 200

    @app.route("/clients/<client_name>/progress", methods=["GET", "POST"])
    def progress(client_name):
        if find_client(client_name) is None:
            return missing_client()
        db = get_db()

        if request.method == "GET":
            rows = db.execute(
                "SELECT week, adherence FROM progress "
                "WHERE client_name = ? ORDER BY id",
                (client_name,),
            ).fetchall()
            return jsonify([dict(row) for row in rows])

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="Send a JSON object."), 400
        week = data.get("week")
        adherence = data.get("adherence")
        if not isinstance(week, str) or not week.strip():
            return jsonify(error="Week is required."), 400
        if (
            not isinstance(adherence, int)
            or isinstance(adherence, bool)
            or not 0 <= adherence <= 100
        ):
            return jsonify(error="Adherence must be an integer from 0 to 100."), 400

        db.execute(
            "INSERT INTO progress (client_name, week, adherence) VALUES (?, ?, ?)",
            (client_name, week.strip(), adherence),
        )
        db.commit()
        return jsonify(week=week.strip(), adherence=adherence), 201

    @app.route("/clients/<client_name>/workouts", methods=["GET", "POST"])
    def workouts(client_name):
        if find_client(client_name) is None:
            return missing_client()
        db = get_db()

        if request.method == "GET":
            rows = db.execute(
                "SELECT * FROM workouts WHERE client_name = ? "
                "ORDER BY date DESC, id DESC",
                (client_name,),
            ).fetchall()
            return jsonify([dict(row) for row in rows])

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="Send a JSON object."), 400
        workout_type = data.get("workout_type")
        duration = data.get("duration_min")
        if not isinstance(workout_type, str) or not workout_type.strip():
            return jsonify(error="Workout type is required."), 400
        if (
            not isinstance(duration, int)
            or isinstance(duration, bool)
            or duration <= 0
        ):
            return jsonify(error="duration_min must be positive."), 400

        workout_date = data.get("date", date.today().isoformat())
        notes = data.get("notes", "")
        cursor = db.execute(
            """
            INSERT INTO workouts
                (client_name, date, workout_type, duration_min, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (client_name, workout_date, workout_type.strip(), duration, notes),
        )
        db.commit()
        return jsonify(id=cursor.lastrowid, **data), 201

    @app.route("/workouts/<int:workout_id>/exercises", methods=["GET", "POST"])
    def exercises(workout_id):
        db = get_db()
        workout = db.execute(
            "SELECT id FROM workouts WHERE id = ?", (workout_id,)
        ).fetchone()
        if workout is None:
            return jsonify(error="Workout not found."), 404

        if request.method == "GET":
            rows = db.execute(
                "SELECT name, sets, reps, weight FROM exercises "
                "WHERE workout_id = ? ORDER BY id",
                (workout_id,),
            ).fetchall()
            return jsonify([dict(row) for row in rows])

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="Send a JSON object."), 400
        name = data.get("name")
        sets = data.get("sets")
        reps = data.get("reps")
        if not isinstance(name, str) or not name.strip():
            return jsonify(error="Exercise name is required."), 400
        if not isinstance(sets, int) or sets <= 0:
            return jsonify(error="Sets must be a positive integer."), 400
        if not isinstance(reps, int) or reps <= 0:
            return jsonify(error="Reps must be a positive integer."), 400

        db.execute(
            "INSERT INTO exercises (workout_id, name, sets, reps, weight) "
            "VALUES (?, ?, ?, ?, ?)",
            (workout_id, name.strip(), sets, reps, data.get("weight")),
        )
        db.commit()
        return jsonify(name=name.strip(), sets=sets, reps=reps,
                       weight=data.get("weight")), 201

    @app.route("/clients/<client_name>/metrics", methods=["GET", "POST"])
    def metrics(client_name):
        if find_client(client_name) is None:
            return missing_client()
        db = get_db()

        if request.method == "GET":
            rows = db.execute(
                "SELECT date, weight, waist, bodyfat FROM metrics "
                "WHERE client_name = ? ORDER BY date DESC",
                (client_name,),
            ).fetchall()
            return jsonify([dict(row) for row in rows])

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="Send a JSON object."), 400
        weight = data.get("weight")
        if not isinstance(weight, (int, float)) or isinstance(weight, bool):
            return jsonify(error="Weight must be a number."), 400

        metric_date = data.get("date", date.today().isoformat())
        db.execute(
            "INSERT INTO metrics (client_name, date, weight, waist, bodyfat) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                client_name,
                metric_date,
                weight,
                data.get("waist"),
                data.get("bodyfat"),
            ),
        )
        db.commit()
        return jsonify(date=metric_date, weight=weight,
                       waist=data.get("waist"), bodyfat=data.get("bodyfat")), 201

    @app.get("/clients/<client_name>/bmi")
    def bmi(client_name):
        row = find_client(client_name)
        if row is None:
            return missing_client()
        if not row["height"] or not row["weight"]:
            return jsonify(error="Client height and weight are required."), 400

        height_m = row["height"] / 100
        value = round(row["weight"] / (height_m * height_m), 1)
        if value < 18.5:
            category = "Underweight"
        elif value < 25:
            category = "Normal"
        elif value < 30:
            category = "Overweight"
        else:
            category = "Obese"
        return jsonify(bmi=value, category=category)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=False,
    )
