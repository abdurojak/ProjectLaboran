from django.db import migrations


def sync_manual_bug_error_schema(apps, schema_editor):
    table_name = 'core_bugerrorlog'
    existing_tables = schema_editor.connection.introspection.table_names(schema_editor.connection.cursor())
    if table_name not in existing_tables:
        return

    with schema_editor.connection.cursor() as cursor:
        columns = {
            column.name
            for column in schema_editor.connection.introspection.get_table_description(cursor, table_name)
        }
        quote = schema_editor.quote_name

        if 'judul' not in columns:
            schema_editor.execute(
                f"ALTER TABLE {quote(table_name)} ADD COLUMN {quote('judul')} varchar(180) NOT NULL DEFAULT ''"
            )
        if 'kategori' not in columns:
            schema_editor.execute(
                f"ALTER TABLE {quote(table_name)} ADD COLUMN {quote('kategori')} varchar(20) NOT NULL DEFAULT 'bug'"
            )
        if 'prioritas' not in columns:
            schema_editor.execute(
                f"ALTER TABLE {quote(table_name)} ADD COLUMN {quote('prioritas')} varchar(20) NOT NULL DEFAULT 'sedang'"
            )
        if 'lokasi' not in columns:
            schema_editor.execute(
                f"ALTER TABLE {quote(table_name)} ADD COLUMN {quote('lokasi')} varchar(500) NOT NULL DEFAULT ''"
            )
        if 'deskripsi' not in columns:
            schema_editor.execute(
                f"ALTER TABLE {quote(table_name)} ADD COLUMN {quote('deskripsi')} longtext NULL"
            )
        if 'langkah_reproduksi' not in columns:
            schema_editor.execute(
                f"ALTER TABLE {quote(table_name)} ADD COLUMN {quote('langkah_reproduksi')} longtext NULL"
            )
        if 'ekspektasi' not in columns:
            schema_editor.execute(
                f"ALTER TABLE {quote(table_name)} ADD COLUMN {quote('ekspektasi')} longtext NULL"
            )
        if 'hasil_aktual' not in columns:
            schema_editor.execute(
                f"ALTER TABLE {quote(table_name)} ADD COLUMN {quote('hasil_aktual')} longtext NULL"
            )
        if 'dilaporkan_oleh_id' not in columns:
            schema_editor.execute(
                f"ALTER TABLE {quote(table_name)} ADD COLUMN {quote('dilaporkan_oleh_id')} bigint NULL"
            )

        with schema_editor.connection.cursor() as refresh_cursor:
            refreshed_columns = {
                column.name
                for column in schema_editor.connection.introspection.get_table_description(refresh_cursor, table_name)
            }

        if {'exception_type', 'judul'}.issubset(refreshed_columns):
            schema_editor.execute(
                f"UPDATE {quote(table_name)} SET {quote('judul')} = LEFT({quote('exception_type')}, 180) "
                f"WHERE {quote('judul')} = ''"
            )
        if {'path', 'lokasi'}.issubset(refreshed_columns):
            schema_editor.execute(
                f"UPDATE {quote(table_name)} SET {quote('lokasi')} = LEFT({quote('path')}, 500) "
                f"WHERE {quote('lokasi')} = ''"
            )
        if {'message', 'deskripsi'}.issubset(refreshed_columns):
            schema_editor.execute(
                f"UPDATE {quote(table_name)} SET {quote('deskripsi')} = {quote('message')} "
                f"WHERE {quote('deskripsi')} = ''"
            )
        if {'pengguna_id', 'dilaporkan_oleh_id'}.issubset(refreshed_columns):
            schema_editor.execute(
                f"UPDATE {quote(table_name)} SET {quote('dilaporkan_oleh_id')} = {quote('pengguna_id')} "
                f"WHERE {quote('dilaporkan_oleh_id')} IS NULL"
            )
        if 'deskripsi' in refreshed_columns:
            schema_editor.execute(
                f"UPDATE {quote(table_name)} SET {quote('deskripsi')} = '' "
                f"WHERE {quote('deskripsi')} IS NULL"
            )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_bugerrorlog'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(sync_manual_bug_error_schema, migrations.RunPython.noop),
            ],
            state_operations=[],
        ),
    ]
