from fastapi import HTTPException, status


def not_found(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)


def bad_request(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)


def forbidden(message: str, payload: dict | None = None) -> HTTPException:
    detail = {"code": message, **(payload or {})}
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def service_unavailable(message: str, payload: dict | None = None) -> HTTPException:
    detail = {"code": message, **(payload or {})}
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)
