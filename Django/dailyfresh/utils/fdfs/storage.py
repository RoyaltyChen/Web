from fdfs_client.client import Fdfs_client

from django.core.files.storage import Storage
from django.conf import settings

class FDFSStorage(Storage):
    """文件存储类"""
    def __init__(self, client_conf=None, base_url=None):
        """初始化"""
        if client_conf is None:
            self.client_conf = settings.FDFS_CLIENT_CONF
        else:
            self.client_conf = client_conf

        if base_url is None:
            self.base_url = 'http://%s:%d' % (settings.FDFS_URL_IP,
                                              settings.FDFS_URL_PORT)
        else:
            self.base_url = base_url

    def _open(self, name, mode='rb'):
        """打开文件"""
        pass

    def _save(self, name, content):
        """
            保存文件
        :param name: 需上传的文件的名字
        :param content: 包含你上传文件内容的File对象
        :return:
        """
        # 创建一个Fdfs_client对象
        client = Fdfs_client(self.client_conf)
        # 上传文件到 fast dfs 系统中
        res = client.upload_by_buffer(content.read())
        # dict
        # {
        #     'Group name': group_name,
        #     'Remote file_id': remote_file_id,
        #     'Status': 'Upload successed.',
        #     'Local file name': '',
        #     'Uploaded size': upload_size,
        #     'Storage IP': storage_ip
        # }
        if res.get('Status') != 'Upload successed.':
            # 上传失败
            raise Exception('上传文件至fast dfs失败')

        # 获取返回的文件ID
        filename = res.get('Remote file_id')

        return filename

    def exists(self, name):
        """Django判断文件名是否可用"""
        # 因为使用的是Fast Dfs文件系统，不保存于本地，并且fast dfs会自动判断内容是否重复，所以文件名任何时候都是可用的。

        return False

    def url(self, name):
        """返回访问文件的url路径"""

        return '{}/{}'.format(self.base_url, name)
