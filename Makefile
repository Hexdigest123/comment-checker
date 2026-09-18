PYTHON ?= python3
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python

.PHONY: all setup install train

all: setup

$(VENV_PYTHON):
	$(PYTHON) -m venv $(VENV)

install: $(VENV_PYTHON) requirements.txt
	$(VENV_PYTHON) -m pip install -r requirements.txt

setup: install

train: setup
	$(VENV_PYTHON) -m utils.train
