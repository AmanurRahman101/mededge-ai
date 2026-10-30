import asyncio
import json
import uuid

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.auth.security import require_role
from app.pipeline.transcribe import CLINICAL_KEYWORDS, LANGUAGE_BIAS

router = APIRouter()


@router.websocket("/api/voice/stream")
async def voice_stream(websocket: WebSocket) -> None:
    await websocket.close(code=1008)
    return
    settings = websocket.app.state.settings
    allowed_origins = {settings.app_base_url.rstrip("/")}
    if settings.app_env != "production":
        allowed_origins.update(origin.rstrip("/") for origin in settings.cors_origin_list)
    if websocket.headers.get("origin", "").rstrip("/") not in allowed_origins:
        await websocket.close(code=1008)
        return
    try:
        require_role(websocket, "doctor")
    except HTTPException:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    if not settings.model_api_key or not settings.model_api_key.get_secret_value():
        await websocket.send_json({"type": "error", "message": "MODEL_API_KEY is not set"})
        await websocket.close()
        return
    import websockets

    uri = f"wss://api.meta.ai/v1/asr/realtime?sessionId=voice-{uuid.uuid4().hex[:8]}"
    try:
        async with websockets.connect(uri, open_timeout=30) as upstream:
            await upstream.send(
                json.dumps(
                    {
                        "authorization": {
                            "accessToken": f"Bearer {settings.model_api_key.get_secret_value()}"
                        },
                        "audioEncoding": "PCM_24KHZ",
                        "model": settings.voice_model,
                        "mode": "PUSH_TO_TALK",
                        "partialMode": "CUMULATIVE",
                        "languageBias": list(LANGUAGE_BIAS),
                        "keywords": list(CLINICAL_KEYWORDS),
                    }
                )
            )
            handshake = json.loads(await upstream.recv())
            await websocket.send_json(handshake)

            async def client_to_meta() -> None:
                while True:
                    message = await websocket.receive()
                    if message.get("bytes") is not None:
                        await upstream.send(message["bytes"])
                    elif message.get("text") is not None:
                        await upstream.send(message["text"])

            async def meta_to_client() -> None:
                async for incoming in upstream:
                    if isinstance(incoming, str):
                        await websocket.send_text(incoming)

            forward = [asyncio.create_task(client_to_meta()), asyncio.create_task(meta_to_client())]
            done, pending = await asyncio.wait(forward, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            for task in done:
                error = task.exception()
                if error and not isinstance(error, WebSocketDisconnect):
                    await websocket.send_json({"type": "error", "message": str(error)[:300]})
    except Exception as exc:  # noqa: BLE001 - report the socket failure to the browser
        try:
            await websocket.send_json({"type": "error", "message": str(exc)[:300]})
        except Exception:
            return
    finally:
        try:
            await websocket.close()
        except Exception:
            return
