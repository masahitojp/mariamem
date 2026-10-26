from django.db import migrations,models
class Migration(migrations.Migration):
    initial=True
    dependencies=[]
    operations=[migrations.CreateModel(name='Order',fields=[
      ('id',models.AutoField(primary_key=True,serialize=False)),
      ('sku',models.CharField(max_length=64,unique=True)),
      ('quantity',models.PositiveIntegerField(default=1))])]
