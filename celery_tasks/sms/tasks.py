from celery_tasks.main import app
from . import constants

@app.task
def send_sms(mobile, number):
    print(number)