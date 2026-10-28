"""Environment parsing shared by local and hosted Django settings."""
from urllib.parse import parse_qsl, unquote, urlsplit

from django.core.exceptions import ImproperlyConfigured


def comma_list(value):
    return [item.strip() for item in value.split(',') if item.strip()]


def postgres_database(url):
    """Accept provider PostgreSQL URLs without logging credentials."""
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in ('postgres', 'postgresql') or not parsed.hostname:
            raise ValueError
        name = unquote(parsed.path.lstrip('/'))
        if not name:
            raise ValueError
        return {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': name,
            'USER': unquote(parsed.username or ''),
            'PASSWORD': unquote(parsed.password or ''),
            'HOST': parsed.hostname,
            'PORT': parsed.port or 5432,
            'CONN_MAX_AGE': 0,
            'DISABLE_SERVER_SIDE_CURSORS': True,
            'OPTIONS': {'connect_timeout': 5, 'sslmode': 'require',
                        **dict(parse_qsl(parsed.query))},
        }
    except ValueError:
        raise ImproperlyConfigured('DATABASE_URL must be a valid PostgreSQL URL.') from None


def hosted_security(env):
    """Fail closed when a Vercel deployment lacks required configuration."""
    secret = env.get('DJANGO_SECRET_KEY', '')
    if len(secret) < 50 or secret.startswith('django-insecure-'):
        raise ImproperlyConfigured('Set DJANGO_SECRET_KEY to a random secret of at least 50 characters.')
    if not env.get('DATABASE_URL'):
        raise ImproperlyConfigured('Set DATABASE_URL to the cloud PostgreSQL connection URL.')
    hosts = comma_list(env.get('DJANGO_ALLOWED_HOSTS', ''))
    for name in ('VERCEL_URL', 'VERCEL_PROJECT_PRODUCTION_URL'):
        if env.get(name) and env[name] not in hosts:
            hosts.append(env[name])
    if not hosts or '*' in hosts:
        raise ImproperlyConfigured('Set DJANGO_ALLOWED_HOSTS to the exact deployment hostname.')
    return {
        'DEBUG': False,
        'SECRET_KEY': secret,
        'ALLOWED_HOSTS': hosts,
        'CSRF_TRUSTED_ORIGINS': comma_list(env.get('DJANGO_CSRF_TRUSTED_ORIGINS', '')),
        'SECURE_PROXY_SSL_HEADER': ('HTTP_X_FORWARDED_PROTO', 'https'),
        'SECURE_SSL_REDIRECT': True,
        'SESSION_COOKIE_SECURE': True,
        'CSRF_COOKIE_SECURE': True,
    }
