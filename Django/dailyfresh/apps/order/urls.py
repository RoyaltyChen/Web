from django.conf.urls import url
from order.views import OrderPlaceView, OrderCommitView, OrderPayView, OrderCheckView, OrderCommentView

urlpatterns = [
    url(r'^place$', OrderPlaceView.as_view(), name='place'),  # 提交订单
    url(r'^commit$', OrderCommitView.as_view(), name='commit'),  # 创建订单
    url(r'^pay$', OrderPayView.as_view(), name='pay'),  # 支付
    url(r'^check$', OrderCheckView.as_view(), name='check'),  # 支付状态检查
    url(r'^comment/(?P<order_id>.+)$', OrderCommentView.as_view(), name='comment'),
]
