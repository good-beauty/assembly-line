from fastapi import FastAPI, Request

app = FastAPI(title="Mock API")

@app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def catch_all(full_path: str, request: Request):
    return {
        "message": "Mock success",
        "path": full_path,
        "method": request.method
    }