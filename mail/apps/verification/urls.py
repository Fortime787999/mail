from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'image_codes/(?P<uuid>[\w-]+)/$', views.ImageCodeView.as_view(), name='image'),
    url(r'sms_codes/(?P<mobile>1[35789][0-9]{9})/$', views.SmsCodeView.as_view(), name='sms'),
]
