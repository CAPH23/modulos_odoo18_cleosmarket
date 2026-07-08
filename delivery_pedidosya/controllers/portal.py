# -*- coding: utf-8 -*-
from odoo import http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal


class PedidosYaCustomerPortal(CustomerPortal):

    @http.route(['/my/orders/<int:order_id>/pedidosya_status'],
                type='http', auth='public', website=True, sitemap=False)
    def pedidosya_portal_status(self, order_id, access_token=None, **kw):
        """Devuelve el progreso del envío en JSON.

        Reutiliza el control de acceso estándar del portal: usuario dueño del
        pedido o access_token válido. Es lo que consume el JS que refresca la
        barra de seguimiento sin recargar la página.
        """
        try:
            order_sudo = self._document_check_access(
                'sale.order', order_id, access_token)
        except (AccessError, MissingError):
            return request.make_json_response({'error': 'access_denied'},
                                              status=403)
        return request.make_json_response(order_sudo.pedidosya_portal_progress())
