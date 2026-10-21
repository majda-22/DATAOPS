PYTHON ?= python

.PHONY: install lint test migrate test-db

install:
	$(PYTHON) -m pip install -e ".[db,dev,spark]"
	$(PYTHON) -m pre_commit install

lint:
	$(PYTHON) scripts/dev.py lint

test:
	$(PYTHON) scripts/dev.py test

migrate:
	$(PYTHON) scripts/dev.py migrate

test-db:
	$(PYTHON) scripts/dev.py test-db
