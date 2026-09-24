"""
routes/api_v1.py
Versioned API v1 surface with generated OpenAPI spec.

All endpoints under /api/v1/ require Bearer token auth.
Error model: {status, message, request_id}
Pagination: list endpoints accept ?page=1&per_page=20 and return
            {items, page, per_page, total}
"""

import logging
import uuid

from flask import Blueprint, jsonify, request, g

from services.auth_service import get_current_user
from services import tenant_service, billing_service
from db.pool import return_connection

logger = logging.getLogger(__name__)


def _error_response(message: str, status_code: int, request_id: str = None):
    """Standard error envelope: {status, message, request_id}."""
    if request_id is None:
        request_id = g.get("request_id", "-")
    return jsonify({
        "status": "error",
        "message": message,
        "request_id": request_id,
    }), status_code


def _paginate(items: list, page: int, per_page: int) -> dict:
    """Build a paginated response envelope."""
    total = len(items)
    start = (page - 1) * per_page
    end = start + per_page
    return {
        "items": items[start:end],
        "page": page,
        "per_page": per_page,
        "total": total,
    }


def _parse_pagination() -> tuple[int, int]:
    """Parse page and per_page from query string, with defaults."""
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = min(100, max(1, int(request.args.get("per_page", 20))))
    except (TypeError, ValueError):
        per_page = 20
    return page, per_page


# ------------------------------------------------------------------ #
# OpenAPI spec (generated as a dict)
# ------------------------------------------------------------------ #

def _build_openapi_spec() -> dict:
    """Build the OpenAPI 3.0 spec for the /api/v1/ surface."""
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Personal AI Assistant API",
            "version": "1.0.0",
            "description": (
                "Versioned API for multi-tenant SaaS operations: tenants, "
                "memberships, subscriptions, billing, and entitlements."
            ),
        },
        "servers": [
            {"url": "/api/v1", "description": "API v1 base URL"},
        ],
        "components": {
            "securitySchemes": {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "description": "Bearer token obtained from /login",
                },
            },
            "schemas": {
                "Error": {
                    "type": "object",
                    "required": ["status", "message"],
                    "properties": {
                        "status": {"type": "string", "example": "error"},
                        "message": {"type": "string"},
                        "request_id": {"type": "string"},
                    },
                },
                "Tenant": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "name": {"type": "string"},
                        "slug": {"type": "string"},
                        "owner_user_id": {"type": "integer"},
                        "created_at": {"type": "string", "format": "date-time"},
                    },
                },
                "TenantCreate": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {
                        "name": {"type": "string", "minLength": 1, "maxLength": 200},
                    },
                },
                "Membership": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "tenant_id": {"type": "integer"},
                        "user_id": {"type": "integer"},
                        "role": {
                            "type": "string",
                            "enum": ["owner", "admin", "member"],
                        },
                        "created_at": {"type": "string", "format": "date-time"},
                    },
                },
                "MembershipCreate": {
                    "type": "object",
                    "required": ["user_id", "role"],
                    "properties": {
                        "user_id": {"type": "integer"},
                        "role": {
                            "type": "string",
                            "enum": ["admin", "member"],
                        },
                    },
                },
                "Subscription": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "tenant_id": {"type": "integer"},
                        "plan": {"type": "string", "enum": ["free", "pro"]},
                        "status": {
                            "type": "string",
                            "enum": ["active", "canceled", "past_due"],
                        },
                        "stripe_subscription_id": {"type": "string", "nullable": True},
                        "current_period_start": {
                            "type": "string", "format": "date-time", "nullable": True,
                        },
                        "current_period_end": {
                            "type": "string", "format": "date-time", "nullable": True,
                        },
                        "created_at": {"type": "string", "format": "date-time"},
                        "updated_at": {"type": "string", "format": "date-time"},
                    },
                },
                "SubscriptionCreate": {
                    "type": "object",
                    "properties": {
                        "plan": {"type": "string", "enum": ["free", "pro"]},
                    },
                },
                "Entitlements": {
                    "type": "object",
                    "properties": {
                        "tenant_id": {"type": "integer"},
                        "plan": {"type": "string"},
                        "ai_daily_limit": {"type": "integer"},
                        "features": {"type": "array", "items": {"type": "string"}},
                        "price_monthly": {"type": "integer"},
                        "status": {"type": "string"},
                    },
                },
                "WebhookPayload": {
                    "type": "object",
                    "required": ["event_id", "event_type"],
                    "properties": {
                        "event_id": {"type": "string"},
                        "event_type": {"type": "string"},
                        "tenant_id": {"type": "integer"},
                        "payload": {"type": "object"},
                    },
                },
                "WebhookResponse": {
                    "type": "object",
                    "properties": {
                        "processed": {"type": "boolean"},
                        "event_id": {"type": "string"},
                        "event_type": {"type": "string"},
                        "subscription": {"$ref": "#/components/schemas/Subscription"},
                    },
                },
                "PaginatedTenants": {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/Tenant"},
                        },
                        "page": {"type": "integer"},
                        "per_page": {"type": "integer"},
                        "total": {"type": "integer"},
                    },
                },
                "PaginatedMemberships": {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/Membership"},
                        },
                        "page": {"type": "integer"},
                        "per_page": {"type": "integer"},
                        "total": {"type": "integer"},
                    },
                },
                "Health": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "example": "ok"},
                        "version": {"type": "string"},
                    },
                },
                "AccountQuota": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "integer"},
                        "plan": {"type": "string", "enum": ["free", "pro", "pro_plus"]},
                        "plan_name": {"type": "string"},
                        "ai_daily_limit": {"type": "integer"},
                        "ai_calls_today": {"type": "integer"},
                        "remaining": {"type": "integer", "nullable": True},
                        "quota_exceeded": {"type": "boolean"},
                    },
                },
            },
        },
        "security": [{"BearerAuth": []}],
        "paths": {
            "/health": {
                "get": {
                    "summary": "Health check",
                    "security": [],
                    "responses": {
                        "200": {
                            "description": "Service is healthy",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Health"},
                                },
                            },
                        },
                    },
                },
            },
            "/openapi.json": {
                "get": {
                    "summary": "OpenAPI specification",
                    "security": [],
                    "responses": {
                        "200": {
                            "description": "OpenAPI 3.0 JSON spec",
                            "content": {
                                "application/json": {"schema": {"type": "object"}},
                            },
                        },
                    },
                },
            },
            "/tenants": {
                "get": {
                    "summary": "List tenants for the authenticated user",
                    "parameters": [
                        {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
                        {"name": "per_page", "in": "query", "schema": {"type": "integer", "default": 20}},
                    ],
                    "responses": {
                        "200": {
                            "description": "Paginated list of tenants",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/PaginatedTenants"},
                                },
                            },
                        },
                        "401": {
                            "description": "Authentication required",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/Error"}},
                            },
                        },
                    },
                },
                "post": {
                    "summary": "Create a new tenant",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/TenantCreate"}},
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Tenant created",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/Tenant"}},
                            },
                        },
                        "400": {
                            "description": "Invalid input",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/Error"}},
                            },
                        },
                        "401": {
                            "description": "Authentication required",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/Error"}},
                            },
                        },
                    },
                },
            },
            "/tenants/{tenant_id}/members": {
                "get": {
                    "summary": "List members of a tenant",
                    "parameters": [
                        {"name": "tenant_id", "in": "path", "required": True, "schema": {"type": "integer"}},
                        {"name": "page", "in": "query", "schema": {"type": "integer", "default": 1}},
                        {"name": "per_page", "in": "query", "schema": {"type": "integer", "default": 20}},
                    ],
                    "responses": {
                        "200": {
                            "description": "Paginated list of memberships",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/PaginatedMemberships"},
                                },
                            },
                        },
                        "403": {
                            "description": "Forbidden — not a member",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/Error"}},
                            },
                        },
                    },
                },
                "post": {
                    "summary": "Add a member to a tenant",
                    "parameters": [
                        {"name": "tenant_id", "in": "path", "required": True, "schema": {"type": "integer"}},
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/MembershipCreate"}},
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Member added",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/Membership"}},
                            },
                        },
                        "403": {
                            "description": "Forbidden — not a member or insufficient role",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/Error"}},
                            },
                        },
                    },
                },
            },
            "/tenants/{tenant_id}/subscription": {
                "get": {
                    "summary": "Get the subscription for a tenant",
                    "parameters": [
                        {"name": "tenant_id", "in": "path", "required": True, "schema": {"type": "integer"}},
                    ],
                    "responses": {
                        "200": {
                            "description": "Subscription details",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/Subscription"}},
                            },
                        },
                        "404": {
                            "description": "No subscription found",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/Error"}},
                            },
                        },
                    },
                },
                "post": {
                    "summary": "Create or update a subscription for a tenant",
                    "parameters": [
                        {"name": "tenant_id", "in": "path", "required": True, "schema": {"type": "integer"}},
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/SubscriptionCreate"}},
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Subscription created",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/Subscription"}},
                            },
                        },
                        "400": {
                            "description": "Invalid plan",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/Error"}},
                            },
                        },
                    },
                },
            },
            "/tenants/{tenant_id}/entitlements": {
                "get": {
                    "summary": "Get entitlements for a tenant",
                    "parameters": [
                        {"name": "tenant_id", "in": "path", "required": True, "schema": {"type": "integer"}},
                    ],
                    "responses": {
                        "200": {
                            "description": "Entitlements",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/Entitlements"}},
                            },
                        },
                    },
                },
            },
            "/billing/webhook": {
                "post": {
                    "summary": "Process a billing webhook (idempotent)",
                    "security": [],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/WebhookPayload"}},
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Webhook processed (or duplicate)",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/WebhookResponse"}},
                            },
                        },
                        "400": {
                            "description": "Invalid webhook payload",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/Error"}},
                            },
                        },
                    },
                },
            },
            "/privacy/export": {
                "get": {
                    "summary": "Export all data for the authenticated user (GDPR)",
                    "responses": {
                        "200": {
                            "description": "User data export",
                            "content": {
                                "application/json": {"schema": {"type": "object"}},
                            },
                        },
                        "401": {
                            "description": "Authentication required",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/Error"}},
                            },
                        },
                    },
                },
            },
            "/privacy/account": {
                "delete": {
                    "summary": "Delete the user account and all associated data (GDPR)",
                    "parameters": [
                        {"name": "confirm", "in": "query", "required": True,
                         "schema": {"type": "string"}, "description": "Pass confirm=true to confirm deletion"},
                    ],
                    "responses": {
                        "200": {
                            "description": "Account deleted",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/Error"}},
                            },
                        },
                        "400": {
                            "description": "Confirmation required",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/Error"}},
                            },
                        },
                    },
                },
            },
            "/api/v1/account/quota": {
                "get": {
                    "summary": "Get the current user plan and remaining quota",
                    "responses": {
                        "200": {
                            "description": "Plan and quota details",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/AccountQuota"}},
                            },
                        },
                        "401": {
                            "description": "Authentication required",
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/Error"}},
                            },
                        },
                    },
                },
            },
        },
    }


# ------------------------------------------------------------------ #
# Blueprint
# ------------------------------------------------------------------ #

def init_api_v1_routes(app, get_connection):
    """Register the /api/v1/ blueprint on the app."""
    api_v1 = Blueprint("api_v1", __name__)

    # ------------------------------------------------------------------ #
    # Health (no auth)
    # ------------------------------------------------------------------ #
    @api_v1.route("/api/v1/health", methods=["GET"])
    def api_health():
        return jsonify({
            "status": "ok",
            "version": "1.0.0",
        })

    # ------------------------------------------------------------------ #
    # OpenAPI spec (no auth)
    # ------------------------------------------------------------------ #
    @api_v1.route("/api/v1/openapi.json", methods=["GET"])
    def api_openapi():
        return jsonify(_build_openapi_spec())

    # ------------------------------------------------------------------ #
    # Tenants — list + create
    # ------------------------------------------------------------------ #
    @api_v1.route("/api/v1/tenants", methods=["GET"])
    def list_tenants():
        user, error, code = get_current_user(get_connection)
        if error:
            return _error_response(error["message"], code)
        try:
            tenants = tenant_service.get_user_tenants(
                user["id"], get_connection
            )
            page, per_page = _parse_pagination()
            result = _paginate(tenants, page, per_page)
            return jsonify(result)
        except Exception:
            logger.error("List tenants error", exc_info=True)
            return _error_response("Could not list tenants", 500)

    @api_v1.route("/api/v1/tenants", methods=["POST"])
    def create_tenant():
        user, error, code = get_current_user(get_connection)
        if error:
            return _error_response(error["message"], code)
        try:
            data = request.get_json(silent=True)
            if not data:
                return _error_response("Request body must be JSON", 400)
            name = str(data.get("name", "")).strip()
            if not name:
                return _error_response("Tenant name is required", 400)
            tenant = tenant_service.create_tenant(
                name, user["id"], get_connection
            )
            return jsonify(tenant), 201
        except ValueError as ve:
            return _error_response(str(ve), 400)
        except Exception:
            logger.error("Create tenant error", exc_info=True)
            return _error_response("Could not create tenant", 500)

    # ------------------------------------------------------------------ #
    # Tenant members — list + add
    # ------------------------------------------------------------------ #
    @api_v1.route("/api/v1/tenants/<int:tenant_id>/members", methods=["GET"])
    def list_members(tenant_id):
        user, error, code = get_current_user(get_connection)
        if error:
            return _error_response(error["message"], code)
        try:
            members = tenant_service.list_members(
                tenant_id, user["id"], get_connection
            )
            page, per_page = _parse_pagination()
            result = _paginate(members, page, per_page)
            return jsonify(result)
        except PermissionError:
            return _error_response(
                "Forbidden — you are not a member of this tenant", 403
            )
        except Exception:
            logger.error("List members error", exc_info=True)
            return _error_response("Could not list members", 500)

    @api_v1.route("/api/v1/tenants/<int:tenant_id>/members", methods=["POST"])
    def add_member(tenant_id):
        user, error, code = get_current_user(get_connection)
        if error:
            return _error_response(error["message"], code)
        try:
            # Verify the requesting user is a member (owner/admin)
            if not tenant_service.check_tenant_access(
                tenant_id, user["id"], get_connection
            ):
                return _error_response(
                    "Forbidden — you are not a member of this tenant", 403
                )
            data = request.get_json(silent=True)
            if not data:
                return _error_response("Request body must be JSON", 400)
            member_user_id = data.get("user_id")
            role = data.get("role", "member")
            if not member_user_id:
                return _error_response("user_id is required", 400)
            membership = tenant_service.add_member(
                tenant_id,
                int(member_user_id),
                role,
                requesting_user_id=user["id"],
                get_connection_fn=get_connection,
            )
            return jsonify(membership), 201
        except ValueError as ve:
            return _error_response(str(ve), 400)
        except Exception:
            logger.error("Add member error", exc_info=True)
            return _error_response("Could not add member", 500)

    # ------------------------------------------------------------------ #
    # Subscription — get + create
    # ------------------------------------------------------------------ #
    @api_v1.route("/api/v1/tenants/<int:tenant_id>/subscription", methods=["GET"])
    def get_subscription(tenant_id):
        user, error, code = get_current_user(get_connection)
        if error:
            return _error_response(error["message"], code)
        try:
            if not tenant_service.check_tenant_access(
                tenant_id, user["id"], get_connection
            ):
                return _error_response(
                    "Forbidden — you are not a member of this tenant", 403
                )
            sub = billing_service.get_subscription(tenant_id, get_connection)
            if not sub:
                return _error_response("No subscription found", 404)
            return jsonify(sub)
        except Exception:
            logger.error("Get subscription error", exc_info=True)
            return _error_response("Could not retrieve subscription", 500)

    @api_v1.route("/api/v1/tenants/<int:tenant_id>/subscription", methods=["POST"])
    def create_subscription(tenant_id):
        user, error, code = get_current_user(get_connection)
        if error:
            return _error_response(error["message"], code)
        try:
            if not tenant_service.check_tenant_access(
                tenant_id, user["id"], get_connection
            ):
                return _error_response(
                    "Forbidden — you are not a member of this tenant", 403
                )
            data = request.get_json(silent=True) or {}
            plan = data.get("plan", "free")
            sub = billing_service.create_subscription(
                tenant_id, plan, get_connection
            )
            return jsonify(sub), 201
        except ValueError as ve:
            return _error_response(str(ve), 400)
        except Exception:
            logger.error("Create subscription error", exc_info=True)
            return _error_response("Could not create subscription", 500)

    # ------------------------------------------------------------------ #
    # Entitlements
    # ------------------------------------------------------------------ #
    @api_v1.route("/api/v1/tenants/<int:tenant_id>/entitlements", methods=["GET"])
    def get_entitlements(tenant_id):
        user, error, code = get_current_user(get_connection)
        if error:
            return _error_response(error["message"], code)
        try:
            if not tenant_service.check_tenant_access(
                tenant_id, user["id"], get_connection
            ):
                return _error_response(
                    "Forbidden — you are not a member of this tenant", 403
                )
            entitlements = billing_service.get_entitlements(
                tenant_id, get_connection
            )
            return jsonify(entitlements)
        except Exception:
            logger.error("Get entitlements error", exc_info=True)
            return _error_response("Could not retrieve entitlements", 500)

    # ------------------------------------------------------------------ #
    # Billing webhook (idempotent, no auth — webhook endpoint)
    # ------------------------------------------------------------------ #
    @api_v1.route("/api/v1/billing/webhook", methods=["POST"])
    def billing_webhook():
        try:
            data = request.get_json(silent=True)
            if not data:
                return _error_response("Request body must be JSON", 400)
            event_id = data.get("event_id")
            event_type = data.get("event_type")
            tenant_id = data.get("tenant_id")
            payload = data.get("payload", data)
            if not event_id:
                return _error_response("event_id is required", 400)
            if not event_type:
                return _error_response("event_type is required", 400)
            result = billing_service.process_webhook(
                event_id, event_type, payload,
                tenant_id=tenant_id,
                get_connection_fn=get_connection,
            )
            return jsonify(result)
        except ValueError as ve:
            return _error_response(str(ve), 400)
        except Exception:
            logger.error("Billing webhook error", exc_info=True)
            return _error_response("Could not process webhook", 500)

    # ------------------------------------------------------------------ #
    # Account quota (M1.5 — release pack: expose plan name + remaining quota)
    # ------------------------------------------------------------------ #
    @api_v1.route("/api/v1/account/quota", methods=["GET"])
    def account_quota():
        user, error, code = get_current_user(get_connection)
        if error:
            return _error_response(error["message"], code)
        try:
            from services.billing_service import get_user_plan, Plan
            from services.usage_service import get_usage
            plan_name = get_user_plan(user["id"], get_connection)
            plan_def = Plan.get(plan_name) or Plan.get("free")
            usage = get_usage(user["id"], get_connection)
            daily_limit = plan_def.get("ai_daily_limit", 0)
            used = usage.get("ai_calls_today", 0)
            remaining = (daily_limit - used) if daily_limit > 0 else None
            return jsonify({
                "user_id": user["id"],
                "plan": plan_name,
                "plan_name": plan_def.get("name", plan_name),
                "ai_daily_limit": daily_limit,
                "ai_calls_today": used,
                "remaining": remaining,
                "quota_exceeded": usage.get("quota_exceeded", False),
            })
        except Exception:
            logger.error("Account quota error", exc_info=True)
            return _error_response("Could not retrieve quota", 500)

    app.register_blueprint(api_v1)
