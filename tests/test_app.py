import pytest

from app import create_app


@pytest.fixture()
def client(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "test.db"),
        }
    )
    return app.test_client()


def create_client(client, **extra):
    payload = {
        "name": "Asha",
        "height": 170,
        "weight": 70,
        "target_weight": 65,
        "target_adherence": 80,
    }
    payload.update(extra)
    return client.post("/clients", json=payload)


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_client_create_list_and_calorie_estimate(client):
    response = create_client(
        client,
        program="Beginner (BG)",
    )
    assert response.status_code == 201
    assert response.get_json()["calories"] == 1820
    assert len(client.get("/clients").get_json()) == 1


def test_duplicate_client_is_rejected(client):
    assert create_client(client).status_code == 201
    assert create_client(client).status_code == 409


def test_progress_validation_and_save(client):
    create_client(client)
    good = client.post(
        "/clients/Asha/progress",
        json={"week": "Week 1", "adherence": 80},
    )
    bad = client.post(
        "/clients/Asha/progress",
        json={"week": "Week 2", "adherence": 120},
    )
    assert good.status_code == 201
    assert bad.status_code == 400
    assert len(client.get("/clients/Asha/progress").get_json()) == 1


def test_workout_and_exercise_logging(client):
    create_client(client)
    workout = client.post(
        "/clients/Asha/workouts",
        json={
            "date": "2026-10-13",
            "workout_type": "Strength",
            "duration_min": 45,
            "notes": "Upper body",
        },
    )
    assert workout.status_code == 201
    workout_id = workout.get_json()["id"]

    exercise = client.post(
        f"/workouts/{workout_id}/exercises",
        json={"name": "Bench press", "sets": 3, "reps": 10, "weight": 40},
    )
    assert exercise.status_code == 201
    assert exercise.get_json()["name"] == "Bench press"


def test_metrics_and_bmi(client):
    create_client(client)
    metric = client.post(
        "/clients/Asha/metrics",
        json={"weight": 70, "waist": 80, "bodyfat": 20},
    )
    bmi = client.get("/clients/Asha/bmi")
    assert metric.status_code == 201
    assert bmi.status_code == 200
    assert bmi.get_json()["bmi"] == 24.2


def test_membership_and_program_generation(client):
    create_client(client, membership_status="Active",
                   membership_end="2026-12-31")
    membership = client.get("/clients/Asha/membership")
    program = client.post(
        "/clients/Asha/program",
        json={"program_type": "Muscle Gain"},
    )
    assert membership.get_json()["membership_status"] == "Active"
    assert program.status_code == 200
    assert program.get_json()["calories"] == 2450


def test_missing_client_returns_404(client):
    response = client.get("/clients/Unknown/membership")
    assert response.status_code == 404
