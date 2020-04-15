from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'register/$', views.RegisterView.as_view(), name='register'),
    url(r'usernames/(?P<username>[a-zA-Z0-9_-]{5,20})/count/$', views.UsernameRepeatView.as_view(), name='namerepeat'),
    url(r'mobiles/(?P<mobile>1[35789][0-9])/count/$', views.MobileRepeatView.as_view(), name='mobilerepeat'),
]
