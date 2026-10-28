"""Isolated settings for local tests; no PostgreSQL or SMTP server required."""
from .settings import *  # noqa: F403

DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
MAILERS = {'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'}}
CACHES = {'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    'LOCATION': 'kyrgyz-tur-tests',
}}
