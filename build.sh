#!/usr/bin/env bash
# Exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Navigate to the Django project directory
cd safeAi

# Collect static files
python manage.py collectstatic --noinput

# Run migrations
python manage.py migrate

# if [[ $CREATE_SUPERUSER ]]
# then
#     python manage.py createsuperuser --no-input
# fi