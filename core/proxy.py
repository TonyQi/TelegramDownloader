from config import GLOBAL_PROXY


def build_proxy_url() -> str:
    scheme = GLOBAL_PROXY["scheme"]
    host = GLOBAL_PROXY["host"]
    port = GLOBAL_PROXY["port"]
    username = GLOBAL_PROXY["username"]
    password = GLOBAL_PROXY["password"]

    auth = ""
    if username and password:
        auth = f"{username}:{password}@"

    return f"{scheme}://{auth}{host}:{port}"


def build_telethon_proxy():
    scheme = GLOBAL_PROXY["scheme"].lower()
    host = GLOBAL_PROXY["host"]
    port = GLOBAL_PROXY["port"]
    username = GLOBAL_PROXY["username"] or None
    password = GLOBAL_PROXY["password"] or None

    if scheme == "socks5":
        return ("socks5", host, port, True, username, password)

    if scheme == "http":
        return ("http", host, port, username, password)

    raise ValueError(f"Unsupported proxy scheme: {scheme}")
