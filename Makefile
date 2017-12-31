PACKAGE=kaoz
SRC_DIR=$(PACKAGE)

# Use current python binary instead of system default.
PYTHON ?= python
COVERAGE = $(PYTHON) $(shell which coverage)
FLAKE8 = flake8
PYTEST = $(shell which pytest)

all: dist

dist:
	$(PYTHON) setup.py sdist

clean:
	find . -type f -name '*.pyc' -delete
	find $(SRC_DIR) -type f -path '*/__pycache__/*' -delete
	find . -type d -empty -delete
	$(RM) -r build dist ./$(PACKAGE).egg-info

update:
	pip install --upgrade pip setuptools
	pip install --upgrade -r requirements_dev.txt
	pip freeze

testall:
	tox

test:
	$(PYTEST) -Wdefault

lint:
	check-manifest
	$(FLAKE8) --config .flake8 $(SRC_DIR)

coverage:
	$(COVERAGE) erase
	$(COVERAGE) run "--include=$(SRC_DIR)/*.py" --branch $(PYTEST)
	$(COVERAGE) report "--include=$(SRC_DIR)/*.py"
	$(COVERAGE) html "--include=$(SRC_DIR)/*.py"

.PHONY: all clean coverage dist lint update test testall
