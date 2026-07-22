# -*- coding: utf-8 -*-
from odoo import api, fields, models


GOBOXFUL_PORTAL_STEPS = [
    ("confirmed", "Pedido confirmado", "fa-check-square-o"),
    ("guide", "Guía creada", "fa-barcode"),
    ("registered", "Envío registrado", "fa-clipboard"),
    ("collected", "Recolectado", "fa-archive"),
    ("transit", "En camino", "fa-truck"),
    ("delivered", "Entregado", "fa-home"),
    ("paid", "Pagado", "fa-money"),
    ("finished", "Finalizado", "fa-flag-checkered"),
]

STATUS_LADDER = {
    -1: 2,
    1: 3,
    2: 4,
    3: 5,
    4: 6,
    11: 5,
}
FINAL_PROBLEM_STATUSES = {5, 6, 7, 8, 9, 10}


class SaleOrder(models.Model):
    _inherit = "sale.order"

    is_goboxful = fields.Boolean(compute="_compute_is_goboxful")
    goboxful_quoted_courier_id = fields.Char(copy=False)
    goboxful_quoted_courier_name = fields.Char(string="Courier cotizado Boxful", copy=False)
    goboxful_quote_price = fields.Monetary(currency_field="currency_id", copy=False)
    goboxful_quote_cod_commission = fields.Monetary(currency_field="currency_id", copy=False)
    goboxful_quote_estimated_delivery = fields.Char(copy=False)
    goboxful_quoted_courier_logo = fields.Char(copy=False)
    goboxful_quoted_max_weight = fields.Float(copy=False)
    goboxful_quoted_delivery_type = fields.Char(copy=False)
    goboxful_quoted_pickup_at = fields.Datetime(string="Recolección estimada Boxful", copy=False)
    goboxful_quote_hash = fields.Char(copy=False)
    goboxful_quote_at = fields.Datetime(copy=False)
    goboxful_quote_options_json = fields.Text(copy=False, groups="base.group_system")
    goboxful_selected_courier_id = fields.Char(
        copy=False,
        help="External id del courier Boxful elegido por el cliente en el checkout. "
             "Vacío significa que se usa el mejor courier según el criterio configurado.",
    )
    goboxful_delivery_status_code = fields.Integer(string="Código de estado Boxful", copy=False)
    goboxful_delivery_status_description = fields.Char(string="Estado de entrega Boxful", copy=False)
    goboxful_delivery_tracking_url = fields.Char(string="Seguimiento Boxful", copy=False)

    @api.depends("carrier_id.delivery_type")
    def _compute_is_goboxful(self):
        for order in self:
            order.is_goboxful = order.carrier_id.delivery_type == "goboxful"

    def _goboxful_has_blocked_products(self):
        self.ensure_one()
        for line in self.order_line:
            if not line.product_id or line.is_delivery or line.product_id.type == "service":
                continue
            category = line.product_id.categ_id
            while category:
                if category.goboxful_block_shipping:
                    return True
                category = category.parent_id
        return False

    def _goboxful_portal_picking(self):
        self.ensure_one()
        return self.picking_ids.filtered(
            lambda p: p.picking_type_code == "outgoing"
            and p.state != "cancel"
            and p.carrier_id.delivery_type == "goboxful"
        ).sorted("id", reverse=True)[:1]

    def goboxful_portal_show_tracking(self):
        self.ensure_one()
        if self.state not in ("sale", "done"):
            return False
        outgoing = self.picking_ids.filtered(
            lambda picking: picking.picking_type_code == "outgoing"
            and picking.state != "cancel"
        )
        if outgoing:
            return bool(outgoing.filtered(
                lambda picking: picking.carrier_id.delivery_type == "goboxful"
            ))
        return bool(self.carrier_id and self.carrier_id.delivery_type == "goboxful")

    def _goboxful_portal_is_paid(self):
        self.ensure_one()
        if self.invoice_ids.filtered(lambda inv: inv.payment_state in ("paid", "in_payment", "reversed")):
            return True
        return bool(self.transaction_ids.filtered(lambda tx: tx.state == "done"))

    def goboxful_portal_progress(self):
        self.ensure_one()
        show = self.goboxful_portal_show_tracking()
        picking = self._goboxful_portal_picking()
        code = picking.goboxful_status_code if picking else False
        problem = code in FINAL_PROBLEM_STATUSES if code is not False else False
        cancelled = code == 5
        ladder = STATUS_LADDER.get(code, 1 if self.state in ("sale", "done") else 0)
        paid = self._goboxful_portal_is_paid()
        delivered = ladder >= 6
        finished = delivered and paid
        done_by_key = {
            "confirmed": ladder >= 1,
            "guide": ladder >= 2,
            "registered": ladder >= 3,
            "collected": ladder >= 4,
            "transit": ladder >= 5,
            "delivered": delivered,
            "paid": paid,
            "finished": finished,
        }
        active_key = False
        if not problem and not finished and show:
            for key, _title, _icon in GOBOXFUL_PORTAL_STEPS:
                if not done_by_key[key]:
                    active_key = key
                    break
        steps = []
        for key, title, icon in GOBOXFUL_PORTAL_STEPS:
            if problem and not done_by_key[key]:
                state = "pending"
                label = "Cancelado" if cancelled else "Requiere atención"
            elif done_by_key[key]:
                state, label = "done", "Completado"
            elif key == active_key:
                state, label = "active", "En progreso"
            else:
                state, label = "pending", "Pendiente"
            steps.append({"key": key, "title": title, "icon": icon,
                          "state": state, "label": label})
        return {
            "show": show,
            "cancelled": cancelled,
            "problem": problem,
            "problem_message": picking.goboxful_status_description if picking else False,
            "finished": finished,
            "tracking_url": picking.goboxful_tracking_url if picking else False,
            "courier_name": picking.goboxful_courier_name if picking else self.goboxful_quoted_courier_name,
            "steps": steps,
        }
