from celery_tasks.main import app
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger('django')


@app.task(bind=True, retry_backoff=3)
def send_active_mail(self, to, verifi_url):
    subject = '美多商城-邮箱激活'
    html_message = '<p>尊敬的用户您好！</p>' \
                   '<p>感谢您使用美多商城。</p>' \
                   '<p>您的邮箱为：%s 。请点击此链接激活您的邮箱：</p>' \
                   '<p><a href="%s">%s<a></p>' \
                   '<p>请于半小时内打开，否则链接将失效<p>' % (to, verifi_url, verifi_url)
    try:
        # subject，message，from_email和recipient_list参数是必需的。
        send_mail(subject, "", from_email=settings.EMAIL_FROM, recipient_list=[to], html_message=html_message)
    except Exception as e:
        logger.info(e)
        self.retry(exc=e, max_retries=3)
