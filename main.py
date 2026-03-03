# main.py 主逻辑：包括字段拼接、模拟请求
import re
import json
import time
import random
import logging
import hashlib
import requests
import urllib.parse
from push import push
from config import data, headers, cookies, READ_NUM, PUSH_METHOD, book, chapter

# 配置日志格式
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)-8s - %(message)s')

# 加密盐及其它默认值
KEY = "3c5c8717f3daf09iop3423zafeqoi"
COOKIE_DATA = {"rq": "%2Fweb%2Fbook%2Fread", "ql": True}
READ_URL = "https://weread.qq.com/web/book/read"
RENEW_URL = "https://weread.qq.com/web/login/renewal"
FIX_SYNCKEY_URL = "https://weread.qq.com/web/book/chapterInfos"


def encode_data(data):
    """数据编码"""
    return '&'.join(f"{k}={urllib.parse.quote(str(data[k]), safe='')}" for k in sorted(data.keys()))


def cal_hash(input_string):
    """计算哈希值"""
    _7032f5 = 0x15051505
    _cc1055 = _7032f5
    length = len(input_string)
    _19094e = length - 1

    while _19094e > 0:
        _7032f5 = 0x7fffffff & (_7032f5 ^ ord(input_string[_19094e]) << (length - _19094e) % 30)
        _cc1055 = 0x7fffffff & (_cc1055 ^ ord(input_string[_19094e - 1]) << _19094e % 30)
        _19094e -= 2

    return hex(_7032f5 + _cc1055)[2:].lower()

def get_wr_skey():
    """刷新cookie密钥"""
    response = requests.post(RENEW_URL, headers=headers, cookies=cookies,
                             data=json.dumps(COOKIE_DATA, separators=(',', ':')))
    for cookie in response.headers.get('Set-Cookie', '').split(';'):
        if "wr_skey" in cookie:
            return cookie.split('=')[-1][:8]
    return None

def fix_no_synckey():
    requests.post(FIX_SYNCKEY_URL, headers=headers, cookies=cookies,
                             data=json.dumps({"bookIds":["3300060341"]}, separators=(',', ':')))

def refresh_cookie():
    logging.info(f"🍪 尝试刷新cookie")
    new_skey = get_wr_skey()
    if new_skey:
        cookies['wr_skey'] = new_skey
        logging.info(f"✅ 密钥刷新成功，新密钥：{new_skey}")
        return True
    else:
        logging.warning("⚠️  无法获取新密钥，使用原有 Cookie")
        return False

# 尝试刷新cookie，如果失败则使用原有cookie
if not refresh_cookie():
    logging.info(f"🔐 使用原有 Cookie:")
    logging.info(f"  wr_vid: {cookies.get('wr_vid', '未找到')}")
    logging.info(f"  wr_skey: {cookies.get('wr_skey', '未找到')}")

index = 1
lastTime = int(time.time()) - 30
logging.info(f"⏱️ 一共需要阅读 {READ_NUM} 次...")

success_count = 0
fail_count = 0
max_retries = 3

while index <= READ_NUM:
    # 复制数据避免修改原数据
    current_data = data.copy()
    current_data.pop('s', None)

    current_data['b'] = random.choice(book)
    current_data['c'] = random.choice(chapter)
    thisTime = int(time.time())
    current_data['ct'] = thisTime
    current_data['rt'] = thisTime - lastTime
    current_data['ts'] = int(thisTime * 1000) + random.randint(0, 1000)
    current_data['rn'] = random.randint(0, 1000)
    current_data['sg'] = hashlib.sha256(f"{current_data['ts']}{current_data['rn']}{KEY}".encode()).hexdigest()
    current_data['s'] = cal_hash(encode_data(current_data))

    logging.info(f"⏱️ 尝试第 {index} 次阅读...")

    try:
        response = requests.post(READ_URL, headers=headers, cookies=cookies,
                                 data=json.dumps(current_data, separators=(',', ':')), timeout=10)
        resData = response.json()

        if 'succ' in resData:
            if 'synckey' in resData:
                lastTime = thisTime
                index += 1
                success_count += 1
                time.sleep(30)
                logging.info(f"✅ 阅读成功，阅读进度：{(index - 1) * 0.5} 分钟")
            else:
                logging.warning("❌ 无synckey, 尝试修复...")
                fix_no_synckey()
                fail_count += 1
                time.sleep(5)
        else:
            logging.warning(f"❌ 响应异常: {resData}")
            # 尝试刷新cookie
            if refresh_cookie():
                logging.info("🔄 Cookie已刷新，重试本次阅读")
            else:
                fail_count += 1
                time.sleep(5)

    except Exception as e:
        logging.error(f"❌ 请求失败: {e}")
        fail_count += 1
        time.sleep(5)

logging.info(f"🎉 阅读脚本已完成！成功: {success_count}, 失败: {fail_count}")

if PUSH_METHOD not in (None, '') and success_count > 0:
    logging.info("⏱️ 开始推送...")
    push(f"🎉 微信读书自动阅读完成！\n⏱️ 阅读时长：{success_count * 0.5}分钟。\n📊 成功: {success_count}次, 失败: {fail_count}次", PUSH_METHOD)
