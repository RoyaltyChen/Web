from django.contrib import admin
from goods.models import GoodsType, Goods, GoodsSKU, GoodsImage, IndexGoodsBanner, IndexPromotionBanner, \
    IndexTypeGoodsBanner
from django.core.cache import cache

# Register your models here.

class BaseModelAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        """新增或更新表中的数据时调用"""
        super().save_model(request, obj, form, change)

        # 发出任务， 让celery worker重新生成首页静态界面
        # print('修改')
        from celery_tasks.tasks import generate_static_index_html
        generate_static_index_html.delay()

        # 清除首页的缓存数据
        cache.delete('index_page_data')

    def delete_model(self, request, obj):
        """删除表中的数据时调用"""
        super().delete_model(request, obj)

        from celery_tasks.tasks import generate_static_index_html
        generate_static_index_html.delay()

        # 清除首页的缓存数据
        cache.delete('index_page_data')


class IndexPromotionBannerAdmin(BaseModelAdmin):
    """模型后台管理类"""
    pass


class GoodsTypeAdmin(BaseModelAdmin):
    pass


class IndexTypeGoodsBannerAdmin(BaseModelAdmin):
    pass


class IndexGoodsBannerAdmin(BaseModelAdmin):
    pass

admin.site.register(GoodsType, GoodsTypeAdmin)
admin.site.register(Goods)
admin.site.register(GoodsSKU)
admin.site.register(GoodsImage)

admin.site.register(IndexGoodsBanner, IndexGoodsBannerAdmin)
admin.site.register(IndexPromotionBanner, IndexPromotionBannerAdmin)
admin.site.register(IndexTypeGoodsBanner, IndexTypeGoodsBannerAdmin)
