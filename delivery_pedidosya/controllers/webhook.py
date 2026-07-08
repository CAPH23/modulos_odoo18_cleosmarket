# -*- coding: utf-8 -*-
"""Receptor de webhooks de PedidosYa (tópico SHIPPING_STATUS).

PedidosYa hace POST a la URL registrada con un JSON (esquema CallbackRequest):

    {
      "topic": "SHIPPING_STATUS",
      "id": "<shippingId>",
      "referenceId": "<referenceId>",
      "generated": "2026-07-04T18:00:00Z",
      "transmitted": "2026-07-04T18:00:05Z",
      "data": {
        "status": "CONFIRMED|IN_PROGRESS|NEAR_PICKUP|PICKED_UP|NEAR_DROPOFF|COMPLETED|CANCELLED",
        "cancelCode": "...", "cancelReason": "...",          # solo CANCELLED
        "estimatedPickUpTime": "...", "estimatedDropOffTime": "..."
      }
    }

y envía en el header Authorization la authorizationKey que definimos al
registrar el webhook. Respuestas: cualquier código != 200 hace que PedidosYa
considere fallida la invocación, por eso los eventos de envíos desconocidos
se responden 200 (ignorado) para no generar reintentos infinitos.
"""

import hmac
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class PedidosYaWebhookController(http.Controller):

    def _json_response(self, payload, status=200):
        return request.make_json_response(payload, status=status)

    def _check_authorization(self, env):
        """Compara el header Authorization contra las claves configuradas en
        los transportistas PedidosYa (comparación en tiempo constante)."""
        received = request.httprequest.headers.get('Authorization') or ''
        if received.lower().startswith('bearer '):
            received = received[7:]
        received = received.strip()
        if not received:
            return False
        carriers = env['delivery.carrier'].sudo().search([
            ('delivery_type', '=', 'pedidosya'),
            ('pedidosya_webhook_key', '!=', False),
        ])
        return any(hmac.compare_digest(received, c.pedidosya_webhook_key)
                   for c in carriers)

    @http.route('/pedidosya/webhook', type='http', auth='public',
                methods=['POST'], csrf=False, save_session=False)
    def pedidosya_webhook(self, **kwargs):
        # --- payload ---------------------------------------------------
        try:
            payload = json.loads(request.httprequest.get_data() or b'{}')
        except (ValueError, UnicodeDecodeError):
            return self._json_response({'error': 'invalid_json'}, status=400)

        # --- autenticación ----------------------------------------------
        if not self._check_authorization(request.env):
            _logger.warning("PedidosYa webhook: clave de autorización inválida "
                            "(IP %s)", request.httprequest.remote_addr)
            return self._json_response({'error': 'unauthorized'}, status=401)

        # --- tópico -------------------------------------------------------
        topic = payload.get('topic')
        if topic and topic != 'SHIPPING_STATUS':
            return self._json_response({'result': 'ignored',
                                        'reason': 'unsupported_topic'})

        shipping_id = payload.get('id')
        status = (payload.get('data') or {}).get('status')
        if not shipping_id or not status:
            return self._json_response({'error': 'missing_id_or_status'},
                                       status=400)

        # --- aplicar ---------------------------------------------------------
        result = request.env['stock.picking'].sudo() \
            ._pedidosya_process_webhook(payload)
        return self._json_response(result)
