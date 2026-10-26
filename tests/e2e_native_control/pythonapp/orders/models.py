from django.db import models
class Order(models.Model):
    sku=models.CharField(max_length=64,unique=True)
    quantity=models.PositiveIntegerField(default=1)
    status=models.CharField(max_length=16,default='ready')
