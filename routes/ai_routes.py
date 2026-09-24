"""
routes/ai_routes.py
AI endpoints: chat, voice transcription, AI-to-task, smart-ai.
All require authentication. Uses centralized AI orchestration layer.
"""

import logging
import os
import tempfile

from flask import Blueprint, jsonify, request

from services.auth_service import get_current_user
from services.ai_service import (
    generate_ai_reply,
    extract_task_from_message,
    decide_smart_action,
    get_openai_client,
)
from services.usage_service import check_and_increment
from services.billing_service import assert_entitlement, EntitlementError
from routes.task_routes import insert_task
from config import settings

logger = logging.getLogger(__name__)


def _ai_provider_configured() -> bool:
    """Return True if an OpenAI API key is configured (non-empty).

    Returns False only when the key is empty or unset, so AI routes can
    return an explicit 'AI provider not configured' error instead of a
    generic 'unavailable'. Does not reject test keys — validation of the
    key's authenticity is the provider's job, not ours.
    """
    key = (settings.OPENAI_API_KEY or "").strip()
    return bool(key)


def _ai_error_response(message: str, status: int = 503) -> tuple:
    """Build a standard AI error JSON response."""
    return jsonify({"status": "error", "message": message}), status


def init_ai_routes(app, get_connection):
    ai_routes = Blueprint("ai_routes", __name__)
    from services.rate_limiter import ai_limit

    @ai_routes.route("/ai", methods=["POST"])
    @ai_limit()
    def ai_chat():
        """Authenticated AI chat."""
        try:
            current_user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            data = request.get_json(silent=True)
            if not data:
                return jsonify({"status": "error", "message": "Request body must be JSON"}), 400

            message = str(data.get("message", "")).strip()
            if not message:
                return jsonify({"status": "error", "message": "Message is required"}), 400

            if len(message) > settings.AI_MAX_INPUT_CHARS:
                return jsonify({
                    "status": "error",
                    "message": f"Message too long (max {settings.AI_MAX_INPUT_CHARS} chars)",
                }), 400

            # M1.1 — Entitlement gate
            try:
                assert_entitlement(current_user["id"], "ai_chat", get_connection)
            except EntitlementError as ee:
                return jsonify({"status": "error", "message": str(ee)}), 403

            allowed, _ = check_and_increment(current_user["id"], get_connection)
            if not allowed:
                return jsonify({
                    "status": "error",
                    "message": "Daily AI request limit reached. Please try again tomorrow.",
                }), 429

            if not _ai_provider_configured():
                return _ai_error_response("AI provider not configured", 503)

            try:
                reply = generate_ai_reply(message)
            except Exception as ai_exc:
                logger.error("AI chat provider error", exc_info=True)
                return _ai_error_response(
                    f"AI service error: {ai_exc}", 503
                )
            return jsonify({"status": "success", "reply": reply})

        except Exception:
            logger.error("AI chat error", exc_info=True)
            return jsonify({"status": "error", "message": "AI service unavailable"}), 503

    @ai_routes.route("/ai-to-task", methods=["POST"])
    @ai_limit()
    def ai_to_task():
        """Extract a task from natural language and create it."""
        try:
            current_user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            data = request.get_json(silent=True)
            if not data:
                return jsonify({"status": "error", "message": "Request body must be JSON"}), 400

            message = str(data.get("message", "")).strip()
            if not message:
                return jsonify({"status": "error", "message": "Message is required"}), 400

            if len(message) > settings.AI_MAX_INPUT_CHARS:
                return jsonify({
                    "status": "error",
                    "message": f"Message too long (max {settings.AI_MAX_INPUT_CHARS} chars)",
                }), 400

            # M1.1 — Entitlement gate
            try:
                assert_entitlement(current_user["id"], "ai_to_task", get_connection)
            except EntitlementError as ee:
                return jsonify({"status": "error", "message": str(ee)}), 403

            # Quota enforcement — ai-to-task also incurs an AI call
            allowed, _ = check_and_increment(current_user["id"], get_connection)
            if not allowed:
                return jsonify({
                    "status": "error",
                    "message": "Daily AI request limit reached. Please try again tomorrow.",
                }), 429

            if not _ai_provider_configured():
                return _ai_error_response("AI provider not configured", 503)

            try:
                extracted = extract_task_from_message(message)
            except Exception as ai_exc:
                logger.error("AI-to-task provider error", exc_info=True)
                return _ai_error_response(
                    f"AI service error: {ai_exc}", 503
                )
            task = insert_task(
                get_connection=get_connection,
                title=extracted["title"],
                description=extracted["description"],
                status=extracted["status"],
                priority=extracted["priority"],
                due_date=extracted.get("due_date"),
                user_id=current_user["id"],
            )
            return jsonify({
                "status": "success",
                "message": "Task created from AI",
                "task": task,
            })

        except ValueError as ve:
            return jsonify({"status": "error", "message": str(ve)}), 400
        except Exception:
            logger.error("AI-to-task error", exc_info=True)
            return jsonify({"status": "error", "message": "AI service unavailable"}), 503

    @ai_routes.route("/smart-ai", methods=["POST"])
    @ai_limit()
    def smart_ai():
        """Authenticated smart AI: decides reply vs task creation."""
        try:
            current_user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            data = request.get_json(silent=True)
            if not data:
                return jsonify({"status": "error", "message": "Request body must be JSON"}), 400

            message = str(data.get("message", "")).strip()
            if not message:
                return jsonify({"status": "error", "message": "Message is required"}), 400

            if len(message) > settings.AI_MAX_INPUT_CHARS:
                return jsonify({
                    "status": "error",
                    "message": f"Message too long (max {settings.AI_MAX_INPUT_CHARS} chars)",
                }), 400

            # M1.1 — Entitlement gate
            try:
                assert_entitlement(current_user["id"], "smart_ai", get_connection)
            except EntitlementError as ee:
                return jsonify({"status": "error", "message": str(ee)}), 403

            allowed, _ = check_and_increment(current_user["id"], get_connection)
            if not allowed:
                return jsonify({
                    "status": "error",
                    "message": "Daily AI request limit reached. Please try again tomorrow.",
                }), 429

            if not _ai_provider_configured():
                return _ai_error_response("AI provider not configured", 503)

            try:
                decision = decide_smart_action(message)
            except Exception as ai_exc:
                logger.error("Smart AI provider error", exc_info=True)
                return _ai_error_response(
                    f"AI service error: {ai_exc}", 503
                )

            if decision["action"] == "task":
                try:
                    task = insert_task(
                        get_connection=get_connection,
                        title=decision["title"],
                        description=decision["description"],
                        status=decision["status"],
                        priority=decision["priority"],
                        due_date=decision.get("due_date"),
                        user_id=current_user["id"],
                    )
                except ValueError as ve:
                    return jsonify({"status": "error", "message": str(ve)}), 400

                return jsonify({
                    "status": "success",
                    "action": "task",
                    "message": "Task created",
                    "task": task,
                })

            return jsonify({
                "status": "success",
                "action": "reply",
                "reply": decision.get("reply", ""),
            })

        except Exception:
            logger.error("Smart AI error", exc_info=True)
            return jsonify({"status": "error", "message": "AI service unavailable"}), 503

    @ai_routes.route("/transcribe-voice", methods=["POST"])
    @ai_limit()
    def transcribe_voice():
        """Authenticated voice transcription via OpenAI Whisper."""
        temp_path = None
        try:
            current_user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            # M1.1 — Entitlement gate (voice)
            try:
                assert_entitlement(current_user["id"], "transcribe_voice", get_connection)
            except EntitlementError as ee:
                return jsonify({"status": "error", "message": str(ee)}), 403

            # Quota enforcement — transcription also incurs an AI call
            allowed, _ = check_and_increment(current_user["id"], get_connection)
            if not allowed:
                return jsonify({
                    "status": "error",
                    "message": "Daily AI request limit reached. Please try again tomorrow.",
                }), 429

            if "audio" not in request.files:
                return jsonify({"status": "error", "message": "Audio file is required"}), 400

            audio_file = request.files["audio"]
            if not audio_file or not audio_file.filename:
                return jsonify({"status": "error", "message": "Invalid audio file"}), 400

            # Read and check size before writing to disk
            audio_data = audio_file.read(settings.VOICE_MAX_UPLOAD_BYTES + 1)
            if len(audio_data) > settings.VOICE_MAX_UPLOAD_BYTES:
                return jsonify({
                    "status": "error",
                    "message": f"Audio file too large (max {settings.VOICE_MAX_UPLOAD_BYTES // (1024*1024)} MB)",
                }), 413

            if len(audio_data) == 0:
                return jsonify({"status": "error", "message": "Audio file is empty"}), 400

            # MIME content-type validation
            content_type = audio_file.content_type or ""
            if content_type not in settings.ALLOWED_AUDIO_MIME_TYPES:
                return jsonify({
                    "status": "error",
                    "message": f"Unsupported audio type: {content_type}. Allowed: {', '.join(settings.ALLOWED_AUDIO_MIME_TYPES)}",
                }), 415

            # Provider check — after input validation, before the AI call
            if not _ai_provider_configured():
                return _ai_error_response("AI provider not configured", 503)

            # Sanitize filename to prevent path traversal
            safe_name = os.path.basename(audio_file.filename)

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

            transcript_text = str(getattr(transcription, "text", "")).strip()
            if not transcript_text:
                return jsonify({"status": "success", "text": ""}), 200

            return jsonify({"status": "success", "text": transcript_text})

        except Exception as exc:
            logger.error("Voice transcription error", exc_info=True)
            return jsonify({
                "status": "error",
                "message": f"Voice processing failed: {exc}",
            }), 503

        finally:
            if temp_path:
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    @ai_routes.route("/voice-to-task", methods=["POST"])
    @ai_limit()
    def voice_to_task():
        """Authenticated voice-to-task: transcribe → extract → return for confirmation."""
        try:
            current_user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            # M1.1 — Entitlement gate (voice)
            try:
                assert_entitlement(current_user["id"], "voice_to_task", get_connection)
            except EntitlementError as ee:
                return jsonify({"status": "error", "message": str(ee)}), 403

            # Quota enforcement — voice-to-task incurs an AI call
            allowed, _ = check_and_increment(current_user["id"], get_connection)
            if not allowed:
                return jsonify({
                    "status": "error",
                    "message": "Daily AI request limit reached. Please try again tomorrow.",
                }), 429

            if "audio" not in request.files:
                return jsonify({"status": "error", "message": "Audio file is required"}), 400

            audio_file = request.files["audio"]
            if not audio_file or not audio_file.filename:
                return jsonify({"status": "error", "message": "Invalid audio file"}), 400

            audio_data = audio_file.read(settings.VOICE_MAX_UPLOAD_BYTES + 1)
            if len(audio_data) > settings.VOICE_MAX_UPLOAD_BYTES:
                return jsonify({
                    "status": "error",
                    "message": f"Audio file too large (max {settings.VOICE_MAX_UPLOAD_BYTES // (1024 * 1024)} MB)",
                }), 413

            if len(audio_data) == 0:
                return jsonify({"status": "error", "message": "Audio file is empty"}), 400

            content_type = audio_file.content_type or ""
            if content_type not in settings.ALLOWED_AUDIO_MIME_TYPES:
                return jsonify({
                    "status": "error",
                    "message": f"Unsupported audio type: {content_type}. Allowed: {', '.join(settings.ALLOWED_AUDIO_MIME_TYPES)}",
                }), 415

            # Provider check — after input validation, before the AI call
            if not _ai_provider_configured():
                return _ai_error_response("AI provider not configured", 503)

            from services.voice_to_task import process_voice_to_task

            result = process_voice_to_task(
                user_id=current_user["id"],
                audio_data=audio_data,
                content_type=content_type,
                get_connection=get_connection,
            )
            return jsonify(result)

        except ValueError as ve:
            return jsonify({"status": "error", "message": str(ve)}), 400
        except Exception as exc:
            logger.error("Voice-to-task error", exc_info=True)
            return jsonify({
                "status": "error",
                "message": f"Voice processing failed: {exc}",
            }), 503

    @ai_routes.route("/voice-to-task/confirm", methods=["POST"])
    @ai_limit()
    def voice_to_task_confirm():
        """Confirm and create a task from a voice-to-task extraction."""
        try:
            current_user, error, code = get_current_user(get_connection)
            if error:
                return jsonify(error), code

            data = request.get_json(silent=True)
            if not data:
                return jsonify({"status": "error", "message": "Request body must be JSON"}), 400

            task_data = data.get("task")
            if not task_data or not task_data.get("title"):
                return jsonify({"status": "error", "message": "Task with title is required for confirmation"}), 400

            from services.voice_to_task import confirm_and_create_task

            task = confirm_and_create_task(
                user_id=current_user["id"],
                task_data=task_data,
                get_connection=get_connection,
            )
            return jsonify({"status": "success", "message": "Task created from voice", "task": task})

        except ValueError as ve:
            return jsonify({"status": "error", "message": str(ve)}), 400
        except Exception:
            logger.error("Voice-to-task confirm error", exc_info=True)
            return jsonify({"status": "error", "message": "Could not create task"}), 503

    app.register_blueprint(ai_routes)
