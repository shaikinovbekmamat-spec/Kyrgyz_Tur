from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from .deployment import hosted_security, postgres_database


class DeploymentSettingsTests(SimpleTestCase):
    def test_database_url_decodes_credentials_and_preserves_tls_options(self):
        config = postgres_database('postgresql://user%40name:p%40ss%3Aword@db.example:5433/travel?sslmode=verify-full&channel_binding=require')
        self.assertEqual(config['USER'], 'user@name')
        self.assertEqual(config['PASSWORD'], 'p@ss:word')
        self.assertEqual(config['HOST'], 'db.example')
        self.assertEqual(config['PORT'], 5433)
        self.assertEqual(config['NAME'], 'travel')
        self.assertEqual(config['OPTIONS']['sslmode'], 'verify-full')
        self.assertEqual(config['OPTIONS']['channel_binding'], 'require')
        self.assertEqual(config['CONN_MAX_AGE'], 0)
        self.assertTrue(config['DISABLE_SERVER_SIDE_CURSORS'])

    def test_database_defaults_to_tls(self):
        config = postgres_database('postgres://user:password@db.example/travel')
        self.assertEqual(config['OPTIONS']['sslmode'], 'require')
        self.assertEqual(config['PORT'], 5432)

    def test_invalid_database_urls_fail_without_disclosing_credentials(self):
        for url in ('sqlite:///db', 'postgres://user:private@/db',
                    'postgres://user:private@host:invalid/db', 'postgres://host/'):
            with self.subTest(url=url):
                with self.assertRaises(ImproperlyConfigured) as error:
                    postgres_database(url)
                self.assertNotIn('private', str(error.exception))

    def test_hosted_settings_use_exact_domains_and_secure_cookies(self):
        config = hosted_security({
            'DJANGO_SECRET_KEY': 'x' * 64, 'DATABASE_URL': 'postgres://host/db',
            'DJANGO_ALLOWED_HOSTS': ' custom.example, ',
            'VERCEL_URL': 'preview.vercel.app',
            'VERCEL_PROJECT_PRODUCTION_URL': 'travel.vercel.app',
            'DJANGO_DEBUG': 'true',
        })
        self.assertFalse(config['DEBUG'])
        self.assertEqual(config['ALLOWED_HOSTS'], ['custom.example', 'preview.vercel.app', 'travel.vercel.app'])
        self.assertTrue(config['SESSION_COOKIE_SECURE'])
        self.assertTrue(config['CSRF_COOKIE_SECURE'])
        self.assertTrue(config['SECURE_SSL_REDIRECT'])

    def test_missing_production_configuration_fails_early(self):
        valid = {'DJANGO_SECRET_KEY': 'x' * 64, 'DATABASE_URL': 'postgres://host/db',
                 'DJANGO_ALLOWED_HOSTS': 'travel.vercel.app'}
        for key in valid:
            with self.subTest(key=key):
                with self.assertRaises(ImproperlyConfigured):
                    hosted_security({**valid, key: ''})
        with self.assertRaises(ImproperlyConfigured):
            hosted_security({**valid, 'DJANGO_ALLOWED_HOSTS': '*'})
