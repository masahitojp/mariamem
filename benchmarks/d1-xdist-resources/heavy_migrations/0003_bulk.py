"""Real bounded DDL/backfill retained in the captured baseline: ~10 MiB payload."""
from django.db import migrations

def populate(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        for table in range(20):
            name = 'resource_seed_%02d' % table
            cursor.execute('CREATE TABLE ' + name + ' (id INT PRIMARY KEY, bucket INT, payload VARCHAR(512), INDEX by_bucket (bucket))')
            for start in range(0, 1000, 250):
                cursor.executemany('INSERT INTO '+name+' VALUES (%s,%s,%s)',
                    [(i, i % 16, ('%04d' % i) + 'x'*508) for i in range(start,start+250)])
            cursor.execute('SELECT COUNT(*), SUM(LENGTH(payload)) FROM '+name)
            assert cursor.fetchone() == (1000, 512000)

class Migration(migrations.Migration):
    dependencies = [('orders', '0002_status')]
    operations = [migrations.RunPython(populate)]
