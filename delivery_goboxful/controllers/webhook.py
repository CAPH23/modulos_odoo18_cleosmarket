# -*- coding: utf-8 -*-
import hmac
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class GoBoxfulWebhookController(http.Controller):

    @http.route(
        "/goboxful/webhook/<int:company_id>",
        type="http", auth="public", methods=["POST"], csrf=False,
        save_session=False,
    )
    def goboxful_webhook(self, company_id, **kwargs):
        account = request.env["goboxful.account"].sudo().search([
            ("company_id", "=", company_id), ("active", "=", True),
        ], limit=1)
        if not account:
            return request.make_json_response({"ok": False, "error": "account_not_found"}, status=404)
        try:
            payload = request.httprequest.get_json(silent=True)
            if not isinstance(payload, dict):
                raw = request.httprequest.get_data(cache=False, as_text=True)
                payload = json.loads(raw or "{}")
        except Exception:
            return request.make_json_response({"ok": False, "error": "invalid_json"}, status=400)

        provided = (
            request.httprequest.headers.get("Authorization")
            or request.httprequest.headers.get("X-Access-Token")
            or request.httprequest.headers.get("X-Webhook-Token")
            or payload.get("accessToken")
            or ""
        )
        if provided.lower().startswith("bearer "):
            provided = provided[7:].strip()
        if not account.webhook_secret or not hmac.compare_digest(
            str(provided), str(account.webhook_secret)
        ):
            _logger.warning("Boxful webhook rechazado para compañía %s", company_id)
            return request.make_json_response({"ok": False, "error": "invalid_secret"}, status=401)
        try:
            result = request.env["stock.picking"].sudo()._goboxful_process_webhook(account, payload)
            return request.make_json_response(result, status=200)
        except Exception:
            _logger.exception("Error procesando webhook Boxful")
            return request.make_json_response({"ok": False, "error": "processing_error"}, status=500)
