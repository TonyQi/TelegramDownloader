import re


PUBLIC_PATTERN = r"https://t\.me/([^/]+)/(?P<msg_id>\d+)"
PRIVATE_PATTERN = r"https://t\.me/c/(?P<chat_id>\d+)/(?P<msg_id>\d+)"


def parse_message_link(url: str):
    url = url.strip()
    m1 = re.fullmatch(PUBLIC_PATTERN, url)
    if m1:
        return m1.group(1), int(m1.group("msg_id"))

    m2 = re.fullmatch(PRIVATE_PATTERN, url)
    if m2:
        chat_id = int("-100" + m2.group("chat_id"))
        return chat_id, int(m2.group("msg_id"))

    raise ValueError("无效的 Telegram 消息链接")
