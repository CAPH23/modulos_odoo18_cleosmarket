# -*- coding: utf-8 -*-
from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def cleo_confirmation_invoice(self):
        """Return the first posted customer invoice related to the order."""
        self.ensure_one()
        invoices = self.invoice_ids.filtered(
            lambda move: move.state == 'posted' and move.move_type in ('out_invoice', 'out_refund')
        ).sorted(lambda move: move.date or move.create_date, reverse=True)
        return invoices[:1]

    def cleo_confirmation_invoice_pdf_url(self):
        """Return portal PDF URL for the posted invoice, or False if there is none."""
        self.ensure_one()
        invoice = self.cleo_confirmation_invoice()
        if not invoice:
            return False
        try:
            return invoice.get_portal_url(report_type='pdf', download=True)
        except Exception:
            return False

    def cleo_confirmation_order_url(self):
        """Return the portal URL for the sale order."""
        self.ensure_one()
        try:
            return self.get_portal_url()
        except Exception:
            return '/my/orders'

    def cleo_confirmation_payment_label(self):
        """Return the latest payment provider label related to the order."""
        self.ensure_one()
        tx = False
        try:
            tx = self.get_portal_last_transaction()
        except Exception:
            tx = self.transaction_ids.sorted(lambda t: t.id, reverse=True)[:1]
        if tx and tx.provider_id:
            return tx.provider_id.name
        return 'Pago confirmado'

    def cleo_confirmation_payment_is_done(self):
        self.ensure_one()
        if self.invoice_ids.filtered(lambda move: move.payment_state in ('paid', 'in_payment')):
            return True
        txs = self.transaction_ids.filtered(lambda tx: tx.state == 'done')
        return bool(txs)

    def cleo_confirmation_delivery_amount(self):
        self.ensure_one()
        delivery_lines = self.order_line.filtered(
            lambda line: not line.display_type and 'is_delivery' in line._fields and line.is_delivery
        )
        return sum(delivery_lines.mapped('price_total')) if delivery_lines else 0.0

    def cleo_confirmation_products_amount(self):
        self.ensure_one()
        return self.amount_total - self.cleo_confirmation_delivery_amount()

    def cleo_confirmation_product_line_count(self):
        self.ensure_one()
        product_lines = self.order_line.filtered(
            lambda line: not line.display_type
            and not ('is_delivery' in line._fields and line.is_delivery)
        )
        return len(product_lines)

    def cleo_confirmation_delivery_text(self):
        self.ensure_one()
        partner = self.partner_shipping_id or self.partner_invoice_id or self.partner_id
        if not partner:
            return ''
        parts = [
            partner.street,
            partner.street2,
            partner.city,
            partner.state_id.name,
            partner.country_id.name,
        ]
        return ', '.join([part for part in parts if part])

    def cleo_confirmation_is_delivered(self):
        self.ensure_one()
        return bool(self.picking_ids.filtered(lambda picking: picking.state == 'done'))

    def cleo_confirmation_is_ready(self):
        """Assigned means reserved/available; useful as a visual signal but not final delivery."""
        self.ensure_one()
        return bool(self.picking_ids.filtered(lambda picking: picking.state == 'assigned'))
