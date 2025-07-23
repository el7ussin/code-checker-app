#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

export FLASK_APP=backend.py
flask db upgrade