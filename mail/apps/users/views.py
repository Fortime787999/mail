from django.contrib.auth import login,authenticate,logout
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.generic import View
from django.conf import settings
import re
from .models import User, Address
from mail.utils.response_code import RETCODE
from . import constants
from django_redis import get_redis_connection
from mail.utils.login import LoginRequiredMixin
from mail.utils import SignatureSerializer
from celery_tasks.email.tasks import send_active_mail
import json
import logging


logger = logging.getLogger('django')


# Create your views here.


class RegisterView(View):

    def get(self, request):
        return render(request, 'register.html')

    def post(self, request):
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        cpassword = request.POST.get('cpwd')
        mobile = request.POST.get('phone')
        sms_code = request.POST.get('msg_code')
        allow = request.POST.get('allow')

        # 判断参数是否传入完整
        if not all([username, password, cpassword, mobile, sms_code, allow]):
            return HttpResponseForbidden('缺少必传参数')
        # 判断用户名是否为5-20个字符
        if not re.match(r'^[a-zA-Z0-9_-]{5,20}$', username):
            return HttpResponseForbidden('用户名为5-20个字符')
        # 判断密码是否为8-20个字符
        if not re.match(r'^[a-zA-Z0-9]{8,20}$', password):
            return HttpResponseForbidden('密码为8-20个字符')
        # 判断两次密码是不是相同
        if password != cpassword:
            return HttpResponseForbidden('请输入相同的密码')
        # 判断手机号是不是符合要求
        if not re.match(r'^1[35789][0-9]{9}$', mobile):
            return HttpResponseForbidden('请输入正确的手机号')
        if User.objects.filter(mobile=mobile):
            return HttpResponseForbidden('手机号已经存在')

        sms_conn = get_redis_connection('sms_code')
        sms_conn_code = sms_conn.get('sms_%s' % mobile)
        if sms_conn_code is None:
            return HttpResponseForbidden('验证码不存在')
        sms_conn.delete('sms_%s' % mobile)
        sms_conn.delete('flags_%s' % mobile)
        if sms_code != sms_conn_code.decode():
            return HttpResponseForbidden('验证码错误')
        # 为什么要再次验证数据呢，防止数据不是从前端发送而来的，是从非正常渠道发送的
        # 保存用户数据
        try:
            user = User.objects.create_user(username=username, password=password, mobile=mobile)
        except Exception as e:
            logger.error(e)
            return render(request, 'register.html', {'register_errmsg': '注册失败'})

        # 创建用户成功，自动登录并返回首页
        login(request, user)
        response = redirect(reverse('contenes:index'))
        response.set_cookie('username', username, max_age=constants.USERNAME_COOKIE_EXPIRES)
        return response


class UsernameRepeatView(View):
    # 判断用户名是否重复
    def get(self, request, username):
        count = User.objects.filter(username=username).count()
        return JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'count': count})


class MobileRepeatView(View):
    # 判断手机号是否重复
    def get(self, request, mobile):
        count = User.objects.filter(mobile=mobile).count()
        return JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'count': count})


class LoginView(View):

    def get(self, request):
        next_url = request.GET.get('next', '/')
        if request.user.is_authenticated:
            return redirect(next_url)
        return render(request, 'login.html')

    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('pwd')
        remembered = request.POST.get('remembered')
        next_url = request.GET.get('next', '/')

        if not all([username, password]):
            return HttpResponseForbidden('缺少传入参数')
            # 判断用户名是否为5-20个字符
        if not re.match(r'^[a-zA-Z0-9_-]{5,20}$', username):
            return HttpResponseForbidden('用户名为5-20个字符')
        # 判断密码是否为8-20个字符
        if not re.match(r'^[a-zA-Z0-9]{8,20}$', password):
            return HttpResponseForbidden('密码为8-20个字符')
        user = authenticate(username=username, password=password)
        if user is None:
            return render(request, 'login.html', {'account_errmsg': '用户名或密码错误'})
        login(request, user)
        if remembered != 'on':
            request.session.set_expiry(0)
        else:
            request.session.set_expiry(None)
        response = redirect(next_url)
        # 向cookie中写入用户名，用于客户端展示
        response.set_cookie('username', username, max_age=constants.USERNAME_COOKIE_EXPIRES)
        return response


class LogoutView(View):

    def get(self, request):
        logout(request)
        response = redirect(reverse('users:login'))
        response.delete_cookie('username')
        return response


class UserInfoView(LoginRequiredMixin, View):

    def get(self, request):
        # 观看前端代码可知，会自动读取登录用户信息，无需发送
        return render(request, 'user_center_info.html')


class EmailActiceView(LoginRequiredMixin, View):

    def put(self, request):
        user = request.user
        json_dict = json.loads(request.body.decode())
        email = json_dict.get('email')

        if not email:
            return HttpResponseForbidden('缺少传入参数')
        if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return HttpResponseForbidden('请填写正确的邮箱格式')
        try:
            user.email = email
            user.save()
        except Exception as e:
            logger.error(e)
            return JsonResponse({'code': RETCODE.DBERR, 'errmsg': '添加邮箱失败'})
        # 发送邮件激活
        # 设置邮件验证地址
        token = {'id': user.id}
        token = SignatureSerializer.dumps(token, constants.EMAIL_ACTIVE_EXPIRES)
        verifi_url = settings.EMAIL_VERIFY_URL + '?token=' + token
        send_active_mail.delay(email, verifi_url)
        return JsonResponse({'code': RETCODE.OK, 'errmsg':'发送激活邮件成功'})


class EmailVeriView(LoginRequiredMixin, View):

    def get(self,request):
        token = request.GET.get('token')
        if not token:
            return HttpResponseForbidden('无效参数')
        token_dict = SignatureSerializer.loads(token, constants.EMAIL_ACTIVE_EXPIRES)
        if token is None:
            return HttpResponseForbidden('无效链接')
        user_id = token_dict.get('id')
        try:
            user = User.objects.get(id=user_id)
            user.email_active = True
            user.save()
        except Exception as e:
            logger.error(e)
            return HttpResponseForbidden('用户不存在')

        return redirect(reverse('users:info'))


class AddressView(LoginRequiredMixin, View):

    def get(self, request):
        address_list = []
        try:
            addresses = request.user.addresses.filter(is_deleted=False)
            for address in addresses:
                address_list.append({
                    'id': address.id,
                    'title': address.title,
                    'receiver': address.receiver,
                    'province_id': address.province_id,
                    'city_id': address.city_id,
                    'district_id': address.district_id,
                    'place': address.place,
                    'mobile': address.mobile,
                    'tel': address.tel,
                    'email': address.email
                })
        except Exception as e:
            logger.error(e)
            return render(request, '404.html')
        else:
            context = {
                'default_address_id': request.user.default_address_id,
                'addresses': address_list,
            }
            return render(request, 'user_center_site.html', context=context)


class AddressCreateView(LoginRequiredMixin, View):

    def post(self, request):
        # 最大地址数为20个，需要判断是否超出
        count = request.user.addresses.count()
        if count > constants.USER_ADDRESS_COUNTS_LIMIT:
            return JsonResponse({'code': RETCODE.THROTTLINGERR, 'errmsg': '地址数量超出上限'})
        data_dict = json.loads(request.body.decode())
        title = data_dict.get('title')
        receiver = data_dict.get('receiver')
        province_id = data_dict.get('province_id')
        city_id = data_dict.get('city_id')
        district_id = data_dict.get('district_id')
        place = data_dict.get('place')
        mobile = data_dict.get('mobile')
        tel = data_dict.get('tel')
        email = data_dict.get('email')
        if not all([title, receiver, province_id, city_id, district_id, place, mobile]):
            return JsonResponse({'code': RETCODE.NECESSARYPARAMERR, 'errmsg': '缺少传入参数'})
        if not re.match(r'^1[345789]\d{9}$', mobile):
            return JsonResponse({'code': RETCODE.MOBILEERR, 'errmsg': '请输入正确的手机号'})
        if tel:
            if not re.match(r'^(0[0-9]{2,3}-)?([2-9][0-9]{6,7})+(-[0-9]{1,4})?$', tel):
                return JsonResponse({'code': RETCODE.TELERR, 'errmsg': '请输入正确的固定号码'})
        if email:
            if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
                return JsonResponse({'code': RETCODE.EMAILERR, 'errmsg': '请输入正确的邮箱地址'})
        try:
            address = Address.objects.create(user = request.user,
                                   title = title,
                                   receiver = receiver,
                                   province_id = province_id,
                                   city_id = city_id,
                                   district_id = district_id,
                                   place = place,
                                   mobile = mobile,
                                   tel = tel,
                                   email = email)
            # 如果没有默认地址，自动设为默认地址
            if not request.user.default_address:
                request.user.default_address = address
                address.save()
        except Exception as e:
            logger.error(e)
            return JsonResponse({'code': RETCODE.DBERR, 'errmsg': '添加地址失败'})
        else:
            address_dict = {
                'id': address.id,
                'title': title,
                'receiver': receiver,
                'province_id': province_id,
                'city_id': city_id,
                'district_id': district_id,
                'place': place,
                'mobile': mobile,
                'tel': tel,
                'email': email
            }
            return JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'address': address_dict})


class AddressDefaultView(LoginRequiredMixin, View):

    def put(self, request, address_id):
        try:
            address = request.user.addresses.get(id=address_id, is_deleted=False)
            request.user.default_address = address
            request.user.save()
        except Exception as e:
            logger.error(e)
            return JsonResponse({'code': RETCODE.NECESSARYPARAMERR, 'errmsg': '数据出错'})
        else:
            return JsonResponse({'code': RETCODE.OK, 'errmsg': '设置默认地址成功'})


class AddressUpdateView(LoginRequiredMixin, View):

    def delete(self, request, address_id):
        try:
            address = request.user.addresses.get(id=address_id, is_deleted=False)
            address.is_deleted = True
            if request.user.default_address == address:
                request.user.default_address = None
                request.user.save()
            address.save()
        except Exception as e:
            logger.error(e)
            return JsonResponse({'code': RETCODE.NECESSARYPARAMERR, 'errmsg': '删除地址失败'})
        else:
            return JsonResponse({'code': RETCODE.OK, 'errmsg': '删除地址成功'})

    def put(self, request, address_id):
        data_dict = json.loads(request.body.decode())
        title = data_dict.get('title')
        receiver = data_dict.get('receiver')
        province_id = data_dict.get('province_id')
        city_id = data_dict.get('city_id')
        district_id = data_dict.get('district_id')
        place = data_dict.get('place')
        mobile = data_dict.get('mobile')
        tel = data_dict.get('tel')
        email = data_dict.get('email')
        if not all([title, receiver, province_id, city_id, district_id, place, mobile]):
            return JsonResponse({'code': RETCODE.NECESSARYPARAMERR, 'errmsg': '缺少传入参数'})
        if not re.match(r'^1[345789]\d{9}$', mobile):
            return JsonResponse({'code': RETCODE.MOBILEERR, 'errmsg': '请输入正确的手机号'})
        if tel:
            if not re.match(r'^(0[0-9]{2,3}-)?([2-9][0-9]{6,7})+(-[0-9]{1,4})?$', tel):
                return JsonResponse({'code': RETCODE.TELERR, 'errmsg': '请输入正确的固定号码'})
        if email:
            if not re.match(r'^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
                return JsonResponse({'code': RETCODE.EMAILERR, 'errmsg': '请输入正确的邮箱地址'})
        try:
            Address.objects.filter(id=address_id).update(user=request.user,
                                             title=title,
                                             receiver=receiver,
                                             province_id=province_id,
                                             city_id=city_id,
                                             district_id=district_id,
                                             place=place,
                                             mobile=mobile,
                                             tel=tel,
                                             email=email)
        except Exception as e:
            logger.error(e)
            return JsonResponse({'code': RETCODE.DBERR, 'errmsg': '修改地址失败'})
        else:
            address_dict = {
                'id': address_id,
                'title': title,
                'receiver': receiver,
                'province_id': province_id,
                'city_id': city_id,
                'district_id': district_id,
                'place': place,
                'mobile': mobile,
                'tel': tel,
                'email': email
            }
            return JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'address': address_dict})





