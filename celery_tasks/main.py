from celery import Celery
from django.conf import settings
import os

# 为celery设置环境变量
os.environ.setdefault('DJANGO_SETTINGS_MODULE','mail.settings.dev')

# 创建一个celery实例
app = Celery('mail')
# 加载celery配置
app.config_from_object('celery_tasks.config')
# 自动注册任务
app.autodiscover_tasks(['celery_tasks.sms'])