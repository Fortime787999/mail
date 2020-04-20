from collections import OrderedDict
from django.shortcuts import render
from django.views.generic import View
from goods.models import GoodsCategory,GoodsChannel, Content,ContentCategory
from mail.utils.categorys import get_category
import logging

logger = logging.getLogger('django')


# Create your views here.


class IndexView(View):

    def get(self, request):
        # {
        #     "1": {
        #         "channels": [
        #             {"id": 1, "name": "手机", "url": "http://shouji.jd.com/"},
        #             {"id": 2, "name": "相机", "url": "http://www.itcast.cn/"}
        #         ],
        #         "sub_cats": [
        #             {
        #                 "id": 38,
        #                 "name": "手机通讯",
        #                 "sub_cats": [
        #                     {"id": 115, "name": "手机"},
        #                     {"id": 116, "name": "游戏手机"}
        #                 ]
        #             },
        #             {
        #                 "id": 39,
        #                 "name": "手机配件",
        #                 "sub_cats": [
        #                     {"id": 119, "name": "手机壳"},
        #                     {"id": 120, "name": "贴膜"}
        #                 ]
        #             }
        #         ]
        #     },
        #     "2": {
        #         "channels": [],
        #         "sub_cats": []
        #     }
        # }
        category_dict = get_category()
        contents = {}
        for content in ContentCategory.objects.all():
            contents[content.key] = content.content_set.filter(status=True).order_by('sequence')
        context = {
            'categories': category_dict,
            'contents': contents
        }
        return render(request, 'index.html', context=context)


