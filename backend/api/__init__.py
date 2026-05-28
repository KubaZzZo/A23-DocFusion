def __getattr__(name: str):
    if name in {"app", "start_api_server"}:
        from api.server import app, start_api_server

        return {"app": app, "start_api_server": start_api_server}[name]
    raise AttributeError(name)


__all__ = ["app", "start_api_server"]
