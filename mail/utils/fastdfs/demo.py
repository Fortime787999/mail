from fdfs_client.client import Fdfs_client

if __name__ == '__main__':
    # 创建连接对象
    client = Fdfs_client('client.conf')
    # 上传文件
    ret = client.upload_by_filename('client.conf')
    # 响应值
    print(ret)