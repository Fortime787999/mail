from django.shortcuts import render
from django.views.generic import View
from mail.utils.login import LoginRequiredMixin
from django.http import HttpResponseForbidden, JsonResponse
from .models import Area
from mail.utils.response_code import RETCODE
import logging

logger = logging.getLogger('django')


# Create your views here.


class AreaView(LoginRequiredMixin, View):

    def get(self, request):
        area_id = request.GET.get('area_id')
        if area_id is None:
            # 需要省份信息
            province_list = []
            try:
                data_list = Area.objects.filter(parent=None)
            except Exception as e:
                logger.error(e)
                return JsonResponse({'code': RETCODE.DBERR, 'errmsg': '数据出错', 'province_list': []})
            else:
                for data in data_list:
                    province_list.append({
                        'id': data.id,
                        'name': data.name,
                    })
                context = {
                    'code': RETCODE.OK,
                    'errmsg': 'OK',
                    'province_list': province_list
                }
                return JsonResponse(context)
        else:
            # 需要市区信息或者县区信息
            try:
                province_data = Area.objects.get(id=area_id)
            except Exception as e:
                logger.error(e)
                return JsonResponse({'code': RETCODE.DBERR, 'errmsg': '数据出错', 'sub_data': {}})
            else:
                try:
                    sub_data_list = Area.objects.filter(parent=province_data)
                except Exception as e:
                    logger.error(e)
                    return JsonResponse({'code': RETCODE.DBERR, 'errmsg': '数据出错', 'sub_data': {}})
                else:
                    sub_data = {'id': province_data.id,
                                'name': province_data.name,
                                'subs': []}
                    for data in sub_data_list:
                        sub_data['subs'].append({
                            'id': data.id,
                            'name': data.name,
                        })
                    context = {
                        'code': RETCODE.OK,
                        'errmsg': 'OK',
                        'sub_data': sub_data,
                    }
                    return JsonResponse(context)
