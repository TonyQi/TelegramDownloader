from config import GLOBAL_PROXY


def default_proxy_settings() -> dict:
    return {
        "enabled": True,
        "scheme": GLOBAL_PROXY["scheme"],
        "host": GLOBAL_PROXY["host"],
        "port": GLOBAL_PROXY["port"],
        "username": GLOBAL_PROXY["username"],
        "password": GLOBAL_PROXY["password"],
    }


def normalize_proxy_settings(proxy_settings=None) -> dict:
    settings = default_proxy_settings()
    if isinstance(proxy_settings, dict):
        settings.update(proxy_settings)

    settings["enabled"] = bool(settings.get("enabled", False))
    settings["scheme"] = str(settings.get("scheme", "socks5")).lower()
    settings["host"] = str(settings.get("host", "")).strip()
    settings["username"] = str(settings.get("username", "")).strip()
    settings["password"] = str(settings.get("password", ""))

    try:
        settings["port"] = int(settings.get("port", 0))
    except (TypeError, ValueError):
        settings["port"] = 0

    return settings


def build_proxy_url(proxy_settings=None) -> str:
    settings = normalize_proxy_settings(proxy_settings)
    if not settings["enabled"]:
        return ""

    auth = ""
    if settings["username"] and settings["password"]:
        auth = f"{settings['username']}:{settings['password']}@"

    return f"{settings['scheme']}://{auth}{settings['host']}:{settings['port']}"


def build_telethon_proxy(proxy_settings=None):
    settings = normalize_proxy_settings(proxy_settings)
    if not settings["enabled"]:
        return None

    scheme = settings["scheme"]
    host = settings["host"]
    port = settings["port"]
    username = settings["username"] or None
    password = settings["password"] or None

    if not host or port <= 0:
        raise ValueError("Proxy host and port are required")

    if scheme == "socks5":
        return ("socks5", host, port, True, username, password)

    if scheme == "http":
        return ("http", host, port, username, password)

    raise ValueError(f"Unsupported proxy scheme: {scheme}")
