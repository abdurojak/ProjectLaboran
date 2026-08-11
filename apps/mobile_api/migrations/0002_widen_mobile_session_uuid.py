from django.db import migrations


def widen_mobile_session_uuid(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != 'mysql':
        return

    table_name = schema_editor.quote_name('mobile_api_mobilesession')
    id_column = schema_editor.quote_name('id')
    with connection.cursor() as cursor:
        # MySQL stores UUIDField as 32 hexadecimal characters, while modern
        # MariaDB sends its native UUID representation with 36 characters.
        cursor.execute(
            f'ALTER TABLE {table_name} MODIFY COLUMN {id_column} char(36) NOT NULL'
        )
        if connection.features.has_native_uuid_field:
            cursor.execute(
                f'''
                UPDATE {table_name}
                SET {id_column} = CONCAT(
                    SUBSTRING({id_column}, 1, 8), '-',
                    SUBSTRING({id_column}, 9, 4), '-',
                    SUBSTRING({id_column}, 13, 4), '-',
                    SUBSTRING({id_column}, 17, 4), '-',
                    SUBSTRING({id_column}, 21, 12)
                )
                WHERE CHAR_LENGTH({id_column}) = 32
                '''
            )


class Migration(migrations.Migration):
    dependencies = [
        ('mobile_api', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(widen_mobile_session_uuid, migrations.RunPython.noop),
    ]
