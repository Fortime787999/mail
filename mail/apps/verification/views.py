from django.shortcuts import render
from django.views.generic import View
from mail.libs.captcha.captcha import captcha
from django_redis import get_redis_connection
from . import constants
from django.http import HttpResponse,JsonResponse
from mail.utils.response_code import RETCODE
import random
# Create your views here.


class ImageCodeView(View):
    def get(self, request, uuid):
        code, text, image_bytes = captcha.generate_captcha()
        image_conn = get_redis_connection('image_code')
        image_conn.setex(uuid, constants.IMAGE_CODE_EXPIRES, text)
        return HttpResponse(image_bytes, content_type='image/jpg')


class SmsCodeView(View):
    def get(self,request,mobile):
        # 接收发送过来的参数
        # 校验参数
        # 完成业务逻辑
        # 返回响应
        image_code = request.GET.get('image_code')
        sms_conn = get_redis_connection('sms_code')
        uuid = request.GET.get('image_code_id')
        flags = sms_conn.get('flags_%s' % mobile)
        if not all([image_code,uuid]):
            return JsonResponse({'code':RETCODE.NECESSARYPARAMERR,'errmsg':'缺少传入参数'})
        if flags is not None:
            return JsonResponse({'code': RETCODE.SMSCODERR, 'errmsg': '请不要重复发送短信'})
        # 进入redis中查询验证码是否存在
        image_conn = get_redis_connection('image_code')
        # 从redis数据库中取出的数据为bytes类型
        image_conn_code = image_conn.get(uuid)
        if image_conn_code is None:
            return JsonResponse({'code': RETCODE.IMAGECODEERR, 'errmsg': '验证码不存在，请重试'})
        # 不区分大小写
        image_conn_code = image_conn_code.decode()
        if image_conn_code.lower() != image_code.lower():
            return JsonResponse({'code': RETCODE.IMAGECODEERR, 'errmsg': '验证码错误，请重试'})
        # 图形验证码验证正确，删除，防止利用单个验证码多次请求
        print(image_conn.delete(uuid))
        # 创建管道，利用管道发送数据，增加服务器利用率，提高效率
        pipe_line = sms_conn.pipeline()
        number = '%06d' % random.randint(0, 999999)
        pipe_line.setex('sms_%s' % mobile, constants.SMS_CODE_EXPIRES, number)
        pipe_line.setex('flags_%s' % mobile, constants.SEND_FLAG, 1)
        pipe_line.execute()
        # 发送短信
        print(number)
        return JsonResponse({'code': RETCODE.OK, 'errmsg': '发送短信成功'})


