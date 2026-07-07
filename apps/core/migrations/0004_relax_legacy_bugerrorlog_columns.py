from django.db import migrations


def relax_legacy_columns(apps, schema_editor):
    table_name = 'core_bugerrorlog'
    with schema_editor.connection.cursor() as cursor:
        existing_tables = schema_editor.connection.introspection.table_names(cursor)
        if table_name not in existing_tables:
            return

        columns = {
            column.name
            for column in schema_editor.connection.introspection.get_table_description(cursor, table_name)
        }
        quote = schema_editor.quote_name

        legacy_columns = {
            'method': 'varchar(12)',
            'path': 'varchar(500)',
            'query_string': 'longtext',
            'exception_type': 'varchar(160)',
            'message': 'longtext',
            'traceback': 'longtext',
        }
        for name, column_type in legacy_columns.items():
            if name in columns:
                schema_editor.execute(
                    f"ALTER TABLE {quote(table_name)} MODIFY COLUMN {quote(name)} {column_type} NULL"
                )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_sync_bugerrorlog_manual_schema'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(relax_legacy_columns, migrations.RunPython.noop),
            ],
            state_operations=[],
        ),
    ]
