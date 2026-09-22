"""
services/voice_to_task.py — End-to-end voice-to-task pipeline.

Flow:
  VOICE → TRANSCRIPTION → TASK EXTRACTION → USER CONFIRMATION → TASK CREATION → VERIFY

Security/privacy:
  - MIME/content-type validation
  - Bounded upload size
  - Temporary file processing — deleted immediately after transcription
  - No sensitive transcript logging
  - Quota/cost accounting via check_and_increment
  - Confirmation step — does NOT auto-create the task
"""

import logging
import os
import tempfile
from typing import Any, Optional

from config import settings
from services.usage_service import check_and_increment

logger = logging.getLogger(__name__)

# Allowed MIME types for audio uploads (from settings)
_ALLOWED_AUDIO_TYPES = set(getattr(settings, "ALLOWED_AUDIO_MIME_TYPES", []))
_MAX_UPLOAD_BYTES = getattr(settings, "VOICE_MAX_UPLOAD_BYTES", 10 * 1024 * 1024)


def _validate_mime(content_type: str) -> None:
    """Validate the MIME type is an allowed audio type."""
    if not content_type:
        raise ValueError("Content-Type is required")
    if content_type not in _ALLOWED_AUDIO_TYPES:
        raise ValueError(
            f"Unsupported audio type: {content_type}. "
            f"Allowed: {', '.join(sorted(_ALLOWED_AUDIO_TYPES))}"
        )


def _validate_size(audio_data: bytes) -> None:
    """Validate the audio data is within the upload size limit."""
    if not audio_data or len(audio_data) == 0:
        raise ValueError("Audio data is empty")
    if len(audio_data) > _MAX_UPLOAD_BYTES:
        raise ValueError(
            f"Audio file too large (max {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB)"
        )


def _transcribe_audio(audio_data: bytes, content_type: str) -> str:
    """
    Transcribe audio data via OpenAI Whisper.

    Uses a temporary file that is deleted immediately after use.
    Does NOT log the transcript content (privacy).
    """
    from services.ai_service import get_openai_client

    # Determine file extension from mime type
    ext = ".webm"
    if "mp4" in content_type or "m4a" in content_type:
        ext = ".mp4"
    elif "ogg" in content_type:
        ext = ".ogg"
    elif "wav" in content_type:
        ext = ".wav"
    elif "mpeg" in content_type or "mp3" in content_type:
        ext = ".mp3"

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(audio_data)
            temp_path = tmp.name

        client = get_openai_client()
        with open(temp_path, "rb") as audio:
            transcription = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio,
                timeout=settings.AI_REQUEST_TIMEOUT,
            )
        # Do NOT log the transcript — it may contain sensitive content
        return str(getattr(transcription, "text", "")).strip()
    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except OSError:
                pass


def _extract_task_from_transcript(transcript: str) -> dict:
    """
    Extract a structured task from the transcript text.

    Uses the existing AI service's extract_task_from_message.
    Does NOT log the transcript.
    """
    from services.ai_service import extract_task_from_message
    return extract_task_from_message(transcript)


def process_voice_to_task(
    user_id: int,
    audio_data: bytes,
    content_type: str,
    get_connection,
) -> dict:
    """
    Process voice audio end-to-end: validate → transcribe → extract task.

    Does NOT auto-create the task. Returns the extracted task for user
    confirmation.

    Flow:
      1. Validate MIME type
      2. Validate file size
      3. Quota check (check_and_increment)
      4. Transcribe via Whisper
      5. Extract task from transcript
      6. Return task for user confirmation

    Returns:
      {
        "status": "success",
        "transcript_length": int,  # we expose length, not content
        "task": {  # extracted task for confirmation
            "title": str,
            "description": str,
            "priority": str,
            "status": "pending",
            "due_date": str | None,
        },
        "needs_confirmation": True,
      }

    Raises:
      ValueError: on validation failures (MIME, size, empty transcript)
    """
    # 1. MIME validation
    _validate_mime(content_type)

    # 2. Size validation
    _validate_size(audio_data)

    # 3. Quota check
    allowed, count = check_and_increment(user_id, get_connection)
    if not allowed:
        raise ValueError("Daily AI request limit reached. Please try again tomorrow.")

    # 4. Transcribe
    transcript = _transcribe_audio(audio_data, content_type)
    if not transcript:
        raise ValueError("Transcription returned empty text")

    # 5. Extract task
    task = _extract_task_from_transcript(transcript)

    # 6. Return for confirmation — do NOT auto-create
    return {
        "status": "success",
        "transcript_length": len(transcript),
        "task": {
            "title": task.get("title", ""),
            "description": task.get("description", ""),
            "priority": task.get("priority", "medium"),
            "status": "pending",
            "due_date": task.get("due_date"),
        },
        "needs_confirmation": True,
    }


def confirm_and_create_task(user_id: int, task_data: dict, get_connection) -> dict:
    """
    Confirm and create a task from the user-confirmed task data.

    This is the second step of the voice-to-task flow: the user reviews
    the extracted task and confirms it, then this function creates it.

    Args:
      user_id: The authenticated user ID
      task_data: The confirmed task dict (title, description, priority, due_date)
      get_connection: DB connection callable

    Returns:
      The created task dict (from insert_task)
    """
    from routes.task_routes import insert_task

    if not task_data or not task_data.get("title"):
        raise ValueError("Task title is required for confirmation")

    task = insert_task(
        get_connection=get_connection,
        title=task_data["title"],
        description=task_data.get("description", ""),
        status="pending",
        priority=task_data.get("priority", "medium"),
        due_date=task_data.get("due_date"),
        user_id=user_id,
    )
    return task
