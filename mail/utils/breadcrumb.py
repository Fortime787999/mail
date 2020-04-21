def get_breadcrumb(category):
    breadcrumb = dict(
        cat1 = '',
        cat2 = '',
        cat3 = '',
    )
    if category.subs.count() == 0:
        # 处于第三级类别
        breadcrumb['cat3'] = category
        cat2 = category.parent
        breadcrumb['cat2'] = cat2
        breadcrumb['cat1'] = cat2.parent
    elif category.parent is None:
        # 处于第一级类别
        breadcrumb['cat1'] = category
    else:
        breadcrumb['cat1'] = category.parent
        breadcrumb['cat2'] = category

    cat1 = breadcrumb['cat1']
    breadcrumb['cat1'] = {
        'url': cat1.goodschannel_set.all()[0].url,
        'name': cat1.name
    }
    return breadcrumb