# -*- coding: utf-8 -*-
from odoo import models

# Etapas de la barra de seguimiento del portal (/my/orders/<id>)
# (clave, título, ícono FontAwesome 4.7)
PY_PORTAL_STEPS = [
    ('taken',          'Orden tomada',                    'fa-clipboard'),
    ('rider_assigned', 'Repartidor asignado',             'fa-user'),
    ('near_pickup',    'Cerca del punto de recolección',  'fa-map-marker'),
    ('picked_up',      'Paquete recolectado',             'fa-archive'),
    ('transit',        'En tránsito',                     'fa-motorcycle'),
    ('near_dropoff',   'Cerca del punto de entrega',      'fa-home'),
    ('delivered',      'Paquete entregado',               'fa-handshake-o'),
    ('paid',           'Pagado',                          'fa-money'),
    ('finished',       'Pedido finalizado',               'fa-flag-checkered'),
]

# Cuántas etapas de la escalera logística (1..6) completa cada estado PedidosYa
PY_STATUS_LADDER = {
    'CONFIRMED': 1,      # orden tomada
    'IN_PROGRESS': 2,    # repartidor asignado ✓
    'NEAR_PICKUP': 3,
    'PICKED_UP': 4,      # recolectado; "en tránsito" queda en progreso
    'NEAR_DROPOFF': 6,   # en tránsito ✓ + cerca de entrega ✓
    'COMPLETED': 7,      # entregado
}


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # ------------------------------------------------------------------
    def _pedidosya_portal_picking(self):
        """Última entrega saliente gestionada con PedidosYa (no cancelada)."""
        self.ensure_one()
        pickings = self.picking_ids.filtered(
            lambda p: p.picking_type_code == 'outgoing'
            and p.state != 'cancel'
            and p.carrier_id.delivery_type == 'pedidosya')
        return pickings.sorted('id', reverse=True)[:1]

    def pedidosya_portal_show_tracking(self):
        """La barra solo se muestra si el método de envío efectivo del pedido
        es PedidosYa; con cualquier otro método queda oculta."""
        self.ensure_one()
        if self.state not in ('sale', 'done'):
            return False
        outgoing = self.picking_ids.filtered(
            lambda p: p.picking_type_code == 'outgoing'
            and p.state != 'cancel')
        if outgoing:
            return bool(outgoing.filtered(
                lambda p: p.carrier_id.delivery_type == 'pedidosya'))
        if not self.carrier_id or self.carrier_id.delivery_type != 'pedidosya':
            return False
        return bool(self.order_line.filtered(lambda l: l.is_delivery))

    def _pedidosya_portal_is_paid(self):
        self.ensure_one()
        if self.invoice_ids.filtered(
                lambda m: m.payment_state in ('paid', 'in_payment', 'reversed')):
            return True
        return bool(self.transaction_ids.filtered(lambda t: t.state == 'done'))

    # ------------------------------------------------------------------
    def pedidosya_portal_progress(self):
        """Estructura consumida por el QWeb del portal y por el endpoint JSON.

        Devuelve::

            {'show': bool, 'cancelled': bool, 'finished': bool,
             'steps': [{'key','title','icon','state','label'}, ...]}

        donde state ∈ done | active | pending.
        """
        self.ensure_one()
        show = self.pedidosya_portal_show_tracking()
        picking = self._pedidosya_portal_picking()
        status = picking.pedidosya_status if picking else False
        cancelled = status == 'CANCELLED'

        # --- escalera logística (etapas 1..6) ---
        if status and status in PY_STATUS_LADDER:
            ladder = PY_STATUS_LADDER[status]
        elif picking and picking.state == 'done':
            ladder = 7                       # entregado aunque no haya estado PY
        elif self.state in ('sale', 'done'):
            ladder = 1                       # la tienda ya tomó la orden
        else:
            ladder = 0

        paid = self._pedidosya_portal_is_paid()
        delivered = ladder >= 7
        finished = delivered and paid

        done_by_key = {
            'taken': ladder >= 1,
            'rider_assigned': ladder >= 2,
            'near_pickup': ladder >= 3,
            'picked_up': ladder >= 4,
            'transit': ladder >= 5,
            'near_dropoff': ladder >= 6,
            'delivered': delivered,
            'paid': paid,
            'finished': finished,
        }

        # Etapa "en progreso": la primera pendiente, solo si hay envío en curso
        # (o el pedido está listo para despachar) y nada está cancelado.
        active_key = False
        if not cancelled and not finished and (picking or ladder >= 1):
            for key, _title, _icon in PY_PORTAL_STEPS:
                if not done_by_key[key]:
                    active_key = key
                    break

        steps = []
        for key, title, icon in PY_PORTAL_STEPS:
            if cancelled and not done_by_key[key]:
                state, label = 'pending', 'Cancelado'
            elif done_by_key[key]:
                state, label = 'done', 'Completado'
            elif key == active_key:
                state, label = 'active', 'En progreso'
            else:
                state, label = 'pending', 'Pendiente'
            steps.append({'key': key, 'title': title, 'icon': icon,
                          'state': state, 'label': label})

        return {
            'show': show,
            'cancelled': cancelled,
            'finished': finished,
            'steps': steps,
        }
