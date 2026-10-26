from django.db import migrations,models
def seed(apps,schema_editor):
    apps.get_model('orders','Order').objects.using(schema_editor.connection.alias).create(sku='SEED',quantity=2)
class Migration(migrations.Migration):
    dependencies=[('orders','0001_initial')]
    operations=[migrations.AddField(model_name='order',name='status',field=models.CharField(default='ready',max_length=16)),migrations.RunPython(seed,migrations.RunPython.noop)]
