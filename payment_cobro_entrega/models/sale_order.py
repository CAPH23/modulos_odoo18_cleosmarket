# -*- coding: utf-8 -*-
import base64
import logging

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    cleo_cod_email_sent = fields.Boolean(
        string='Cobro contra entrega email sent',
        copy=False,
        readonly=True,
        help='Technical field used to avoid sending the cash on delivery email more than once.',
    )

    def _cleo_cod_get_ticket_filename(self):
        """Return the PDF filename used for the purchase ticket attachment."""
        self.ensure_one()
        safe_order_name = (self.name or 'pedido').replace('/', '-')
        return _('Ticket de compra - %s.pdf') % safe_order_name

    def _cleo_cod_render_sale_order_ticket_pdf(self):
        """Render Odoo's standard sale order PDF to use it as purchase ticket.

        The public website order confirmation email uses this PDF as the customer's
        purchase ticket. We call the report service directly instead of depending on
        mail.template report fields, because those fields can vary between Odoo versions.
        """
        self.ensure_one()
        report_service = self.env['ir.actions.report'].sudo()

        # Odoo 17/18 style API.
        try:
            pdf_content, _content_type = report_service._render_qweb_pdf(
                'sale.action_report_saleorder',
                res_ids=[self.id],
            )
            return pdf_content
        except Exception as first_error:
            _logger.debug(
                'Could not render sale order report with report service API for %s: %s',
                self.name,
                first_error,
            )

        # Fallback for installations where _render_qweb_pdf is called on the report record.
        report = self.env.ref('sale.action_report_saleorder', raise_if_not_found=False)
        if not report:
            _logger.warning('Cobro contra entrega: sale.action_report_saleorder report was not found.')
            return False
        try:
            pdf_content, _content_type = report.sudo()._render_qweb_pdf([self.id])
            return pdf_content
        except Exception:
            _logger.exception(
                'Cobro contra entrega: could not render purchase ticket PDF for sale order %s.',
                self.name,
            )
            return False

    def _cleo_cod_get_or_create_ticket_attachment(self):
        """Create or reuse the purchase ticket PDF attachment for this sale order."""
        self.ensure_one()
        filename = self._cleo_cod_get_ticket_filename()
        Attachment = self.env['ir.attachment'].sudo()

        attachment = Attachment.search([
            ('res_model', '=', 'sale.order'),
            ('res_id', '=', self.id),
            ('name', '=', filename),
        ], limit=1)
        if attachment:
            return attachment

        pdf_content = self._cleo_cod_render_sale_order_ticket_pdf()
        if not pdf_content:
            return Attachment.browse()

        return Attachment.create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(pdf_content),
            'res_model': 'sale.order',
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })

    def _cleo_cod_send_pending_payment_email(self):
        """Send the customer-facing cash-on-delivery payment notice once per order.

        The email includes the sale order PDF as the customer's purchase ticket.
        """
        template = self.env.ref(
            'payment_cobro_entrega.mail_template_cobro_entrega_sale_order',
            raise_if_not_found=False,
        )
        if not template:
            return

        for order in self.sudo():
            if order.cleo_cod_email_sent or not order.partner_id.email:
                continue

            email_values = {}
            ticket_attachment = order._cleo_cod_get_or_create_ticket_attachment()
            if ticket_attachment:
                email_values['attachment_ids'] = [(4, ticket_attachment.id)]
            else:
                _logger.warning(
                    'Cobro contra entrega: email for order %s will be sent without purchase ticket attachment.',
                    order.name,
                )

            template.sudo().send_mail(
                order.id,
                force_send=True,
                email_values=email_values,
            )
            order.cleo_cod_email_sent = True
