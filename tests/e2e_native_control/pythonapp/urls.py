import os
from django.urls import path
from django.http import JsonResponse
from django.shortcuts import render,redirect
from django import forms
from django.db import connection
from orders.models import Order
class OrderForm(forms.ModelForm):
    class Meta:
        model=Order
        fields=['sku','quantity']
        labels={'sku':'SKU','quantity':'Quantity'}
def orders(request):
    form=OrderForm(request.POST if request.method=='POST' else None)
    if request.method=='POST' and form.is_valid():
        form.save()
        return redirect('/orders?created=1')
    return render(request,'orders/index.html',{'form':form,'orders':Order.objects.order_by('id'),'created':request.GET.get('created')=='1'})
def health(request):
    with connection.cursor() as cursor:
        cursor.execute('SELECT VERSION(),DATABASE()')
        version,name=cursor.fetchone()
    return JsonResponse({'pid':os.getpid(),'db_version':version,'db_name':name})
urlpatterns=[path('orders',orders),path('healthz',health)]
