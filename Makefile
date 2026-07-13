# The targets the CI pipelines in the labs call.
.PHONY: install test lint run build
install:            ## install runtime + dev deps
	pip install -r requirements.txt -r requirements-dev.txt
test:               ## run the test suite
	pytest -q
lint:               ## basic syntax/compile check (swap for ruff/flake8 in real life)
	python -m py_compile main.py
run:                ## run locally with autoreload
	uvicorn main:app --reload --port 8080
build:              ## build the container image
	docker build -t cascade:dev .
