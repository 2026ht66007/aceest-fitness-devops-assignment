# ACEest Fitness & Gym

A Flask and SQLite fitness-management app adapted from selected features in
the supplied ACEest versions 2.2.4 and 3.2.4. The original Tkinter screens
were replaced with Flask routes.

## Features

- Client profiles and calorie estimates
- Weekly adherence tracking
- Workouts and exercises
- Body metrics and BMI
- Membership details
- Fitness program generation

## Local setup

Create and activate a virtual environment, then install the dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Start the application:

```bash
PORT=5001 python app.py
```

Open <http://localhost:5001/> or check <http://localhost:5001/health>.

## Run tests

```bash
pytest -q
```

## Docker

Build and run the app:

```bash
docker build -t aceest-fitness .
docker run --rm -p 5001:5000 aceest-fitness
```

Run tests inside the image:

```bash
docker run --rm aceest-fitness pytest -q
```

## GitHub Actions

The workflow at `.github/workflows/main.yml` runs on pushes and pull requests.
It checks Python syntax, builds the Docker image, and runs pytest inside the
container.

## Jenkins

The Jenkins job checks out the `main` branch, builds the Docker image, checks
Python syntax, and runs pytest inside the container.
