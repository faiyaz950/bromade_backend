from django.db.backends.mysql.base import DatabaseWrapper as MySQLDatabaseWrapper


class DatabaseWrapper(MySQLDatabaseWrapper):
    """Django's MySQL backend without the MySQL 8 minimum-version gate.

    BigRock shared hosting runs MySQL 5.7. Django still feature-detects by
    server version, so the schema and queries fall back to 5.7-compatible SQL;
    only the hard refusal at connect time is skipped.
    """

    def check_database_version_supported(self):
        pass
