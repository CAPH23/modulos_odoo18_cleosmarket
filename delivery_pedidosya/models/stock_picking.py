# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

PEDIDOSYA_STATUSES = [
    ('REJECTED', 'Rechazado'),
    ('CONFIRMED', 'Confirmado'),
    ('IN_PROGRESS', 'Repartidor asignado'),
    ('NEAR_PICKUP', 'Cerca del punto de recogida'),
    ('PICKED_UP', 'Paquete recogido'),
    ('NEAR_DROPOFF', 'Cerca de la entrega'),
    ('COMPLETED', 'Entregado'),
    ('CANCELLED', 'Cancelado'),
]
PEDIDOSYA_FINAL_STATUSES = ['REJECTED', 'COMPLETED', 'CANCELLED']

# Orden lógico de la vida del envío (para descartar webhooks fuera de orden)
PEDIDOSYA_STATUS_RANK = {
    'CONFIRMED': 1,
    'IN_PROGRESS': 2,
    'NEAR_PICKUP': 3,
    'PICKED_UP': 4,
    'NEAR_DROPOFF': 5,
    'COMPLETED': 6,
}


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    is_pedidosya = fields.Boolean(compute='_compute_is_pedidosya')
    pedidosya_shipping_id = fields.Char(string='PedidosYa Shipping ID', copy=False)
    pedidosya_confirmation_code = fields.Char(
        string='Código de confirmación', copy=False,
        help="Usar este código al contactar al call center de PedidosYa.")
    pedidosya_status = fields.Selection(
        selection=PEDIDOSYA_STATUSES, string='Estado PedidosYa', copy=False)
    pedidosya_tracking_url = fields.Char(string='URL de seguimiento', copy=False)

    @api.depends('carrier_id.delivery_type')
    def _compute_is_pedidosya(self):
        for picking in self:
            picking.is_pedidosya = picking.carrier_id.delivery_type == 'pedidosya'

    # ------------------------------------------------------------------
    def action_pedidosya_refresh_status(self):
        """Consulta GET /v3/shippings/{id} y actualiza el estado local."""
        for picking in self:
            if not (picking.pedidosya_shipping_id and picking.is_pedidosya):
                continue
            client = picking.carrier_id._pedidosya_get_client()
            data = client.get_shipping(picking.pedidosya_shipping_id)
            new_status = data.get('status')
            if new_status and new_status != picking.pedidosya_status:
                picking.pedidosya_status = new_status
                picking.message_post(body=_(
                    "PedidosYa: el envío pasó a estado <b>%s</b>.", new_status))
        return True

    def action_pedidosya_open_tracking(self):
        self.ensure_one()
        if not self.pedidosya_tracking_url:
            return False
        return {
            'type': 'ir.actions.act_url',
            'url': self.pedidosya_tracking_url,
            'target': 'new',
        }

    # ------------------------------------------------------------------
    @api.model
    def _pedidosya_process_webhook(self, payload):
        """Aplica un callback SHIPPING_STATUS al picking correspondiente.

        Protección contra eventos fuera de orden: los estados solo avanzan
        (según su rango); CANCELLED se aplica siempre. Los shippingId
        desconocidos se ignoran con respuesta OK para evitar reintentos.
        """
        shipping_id = payload.get('id')
        data = payload.get('data') or {}
        status = data.get('status')

        picking = self.search([('pedidosya_shipping_id', '=', shipping_id)],
                              limit=1)
        if not picking:
            _logger.warning("PedidosYa webhook: shippingId desconocido %s",
                            shipping_id)
            return {'result': 'ignored', 'reason': 'unknown_shipping_id'}

        if status not in PEDIDOSYA_STATUS_RANK and status != 'CANCELLED':
            picking.message_post(body=_(
                "PedidosYa: evento no reconocido recibido por webhook: "
                "<b>%s</b>.", status))
            return {'result': 'ignored', 'reason': 'unknown_status'}

        current_rank = PEDIDOSYA_STATUS_RANK.get(picking.pedidosya_status, 0)
        new_rank = PEDIDOSYA_STATUS_RANK.get(status, 0)
        if status != 'CANCELLED' and new_rank <= current_rank:
            return {'result': 'ignored', 'reason': 'out_of_order'}

        picking.pedidosya_status = status
        if status == 'CANCELLED':
            picking.message_post(body=_(
                "PedidosYa (webhook): envío <b>CANCELADO</b>.<br/>"
                "Código: %(code)s<br/>Motivo: %(reason)s",
                code=data.get('cancelCode') or '-',
                reason=data.get('cancelReason') or '-'))
        else:
            eta = data.get('estimatedDropOffTime') or \
                data.get('estimatedPickUpTime')
            picking.message_post(body=_(
                "PedidosYa (webhook): el envío pasó a estado <b>%(status)s</b>."
                "%(eta)s",
                status=status,
                eta=eta and _(" ETA: %s", eta) or ''))
        return {'result': 'ok', 'picking': picking.name, 'status': status}

    # ------------------------------------------------------------------
    @api.model
    def _cron_pedidosya_sync_status(self):
        """Respaldo por sondeo mientras no estén activos los webhooks (Fase 2)."""
        pickings = self.search([
            ('pedidosya_shipping_id', '!=', False),
            ('pedidosya_status', 'not in', PEDIDOSYA_FINAL_STATUSES),
        ], limit=100)
        for picking in pickings:
            try:
                picking.action_pedidosya_refresh_status()
            except Exception:
                _logger.exception(
                    "PedidosYa: fallo sincronizando estado del picking %s",
                    picking.name)
