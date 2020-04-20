from collections import OrderedDict
from goods.models import GoodsCategory,GoodsChannel

def get_category():
    category_dict = OrderedDict()
    channel_list = GoodsChannel.objects.order_by('group_id', 'sequence')
    # 提取频道组  group_id,构建字典
    for channel in channel_list:
        group_id = channel.group_id
        # 说明该频道不在返回字典中
        if group_id not in category_dict:
            category_dict[group_id] = {'channels': [], 'sub_cats': []}
        category = GoodsCategory.objects.get(id=channel.category_id)
        category_dict[group_id]['channels'].append({'id': category.id, 'name': category.name, 'url': channel.url})
        # 二级类别
        for sub_cat2 in category.subs.all():
            sub_cats = []
            for sub_cat3 in sub_cat2.subs.all():
                sub_cats.append({'id': sub_cat3.id, 'name': sub_cat3.name})
            category_dict[group_id]['sub_cats'].append({'id': sub_cat2.id, 'name': sub_cat2.name, 'sub_cats': sub_cats})
    return category_dict