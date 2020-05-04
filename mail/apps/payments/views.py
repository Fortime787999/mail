from django.shortcuts import render
from django.conf import settings
from django.views.generic import View
from orders.models import OrderInfo
from alipay import AliPay
from mail.utils.response_code import RETCODE
from .models import Payment
from django.http import JsonResponse, Http404, HttpResponseBadRequest, HttpResponseServerError
from alipay.aop.api.AlipayClientConfig import AlipayClientConfig
from alipay.aop.api.DefaultAlipayClient import DefaultAlipayClient
from alipay.aop.api.domain.AlipayTradePagePayModel import AlipayTradePagePayModel
from alipay.aop.api.request.AlipayTradePagePayRequest import AlipayTradePagePayRequest
from alipay.aop.api.domain.SettleDetailInfo import SettleDetailInfo

import os
import logging

logger = logging.getLogger('django')


# Create your views here.


class GetUrlView(View):

    def get(self, request, order_id):
        # 验证订单编号
        try:
            order = OrderInfo.objects.get(pk=order_id)
        except:
            return Http404('订单编号无效')
        # 创建支付宝对象
        app_private_key_string = open(os.path.join(settings.BASE_DIR, 'libs/alipay/app_private_key.pem')).read()
        alipay_public_key_string = open(os.path.join(settings.BASE_DIR, 'libs/alipay/alipay_public_key.pem')).read()
        alipay = AliPay(
            appid=settings.ALIPAY_APPID,
            app_notify_url=None,
            app_private_key_string=app_private_key_string,
            alipay_public_key_string=alipay_public_key_string,
            sign_type="RSA2",
            debug=settings.ALIPAY_DEBUG
        )
        # 生成支付的参数
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id,
            total_amount=str(order.total_amount),
            subject='美多商城在-订单支付',
            return_url=settings.ALIPAY_RETURN_URL
        )
        # 拼接最终的支付地址
        alipay_url = settings.ALIPAY_URL + '?' + order_string
        # 响应
        return JsonResponse({
            'code': RETCODE.OK,
            'errmsg': 'OK',
            'alipay_url': alipay_url
        })
    # def get(self, request, order_id):
    #     app_private_key_string = open(os.path.join(settings.BASE_DIR, 'libs/alipay/app_private_key.pem')).read()
    #     alipay_public_key_string = open(os.path.join(settings.BASE_DIR, 'libs/alipay/alipay_public_key.pem')).read()
    #     try:
    #         order = OrderInfo.objects.get(order_id=order_id)
    #     except Exception as e:
    #         logger.error(e)
    #         return JsonResponse({'code': RETCODE.DBERR, 'errmsg': '无效订单编号'})
    #
    #     alipay_client_config = AlipayClientConfig()
    #     alipay_client_config.server_url = settings.ALIPAY_URL
    #     alipay_client_config.app_id = settings.ALIPAY_APPID
    #     alipay_client_config.return_url = settings.ALIPAY_RETURN_URL
    #     alipay_client_config.app_private_key = app_private_key_string,
    #     alipay_client_config.alipay_public_key = alipay_public_key_string,
    #     client = DefaultAlipayClient(alipay_client_config=alipay_client_config, logger=logger)
    #
    #     model = AlipayTradePagePayModel()
    #     model.out_trade_no = order_id
    #     model.total_amount = str(order.total_amount)
    #     model.subject = '美多商城-订单支付'
    #     model.product_code = "FAST_INSTANT_TRADE_PAY"
    #
    #     url = AlipayTradePagePayRequest(biz_model=model)
    #     response = client.page_execute(url, http_method="GET")
    #     return JsonResponse({'code': RETCODE.OK, 'errmsg': 'OK', 'alipay_url': response})


class PayStatusView(View):

    def get(self, request):
        data = request.GET.dict()

        signature = data.pop("sign")

        app_private_key_string = open(os.path.join(settings.BASE_DIR, 'libs/alipay/app_private_key.pem')).read()
        alipay_public_key_string = open(os.path.join(settings.BASE_DIR, 'libs/alipay/alipay_public_key.pem')).read()
        alipay = AliPay(
            appid=settings.ALIPAY_APPID,
            app_notify_url=None,
            app_private_key_string=app_private_key_string,
            alipay_public_key_string=alipay_public_key_string,
            sign_type="RSA2",
            debug=settings.ALIPAY_DEBUG
        )
        # verification
        success = alipay.verify(data, signature)
        if not success:
            # 如果支付失败，则提示
            return HttpResponseBadRequest('支付失败，请重新支付')
        out_trade_no = data.get('out_trade_no')
        trade_no = data.get('trade_no')
        try:
            Payment.objects.create(order_id=out_trade_no, trade_id=trade_no)
            OrderInfo.objects.filter(pk=out_trade_no).update(status=OrderInfo.ORDER_STATUS_ENUM['UNCOMMENT'])
        except Exception as e:
            logger.error(e)
            return HttpResponseServerError('出现异常，请重试')

        context = {
            'trade_no': trade_no
        }
        return render(request, 'pay_success.html', context=context)
