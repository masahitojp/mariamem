from django.db import migrations


class Migration(migrations.Migration):
    atomic = False
    dependencies = [('orders', '0002_status')]
    operations = [
        migrations.RunSQL('CREATE TABLE w3_partial_ddl (n INT PRIMARY KEY) ENGINE=InnoDB'),
        migrations.RunSQL('INSERT INTO w3_missing_migration_table VALUES (1)'),
    ]
