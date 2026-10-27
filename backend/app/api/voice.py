import asyncio
import json
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.pipeline.transcribe import CLINICAL_KEYWORDS, LANGUAGE_BIAS

router = APIRouter()


@router.websocket("/api/voice/stream")
async def voice_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    settings = websocket.app.state.settings
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

            done = await asyncio.gather(client_to_meta(), meta_to_client(), return_exceptions=True)
            for item in done:
                if isinstance(item, Exception) and not isinstance(item, WebSocketDisconnect):
                    await websocket.send_json({"type": "error", "message": str(item)[:300]})
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
