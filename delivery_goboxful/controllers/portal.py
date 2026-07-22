# -*- coding: utf-8 -*-
from odoo import http
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal


class GoBoxfulCustomerPortal(CustomerPortal):

    @http.route(
        ["/my/orders/<int:order_id>/goboxful_status"],
        type="http", auth="public", website=True, sitemap=False,
    )
    def goboxful_portal_status(self, order_id, access_token=None, **kwargs):
        try:
            order = self._document_check_access("sale.order", order_id, access_token)
        except (AccessError, MissingError):
            return request.make_json_response({"error": "access_denied"}, status=403)
        return request.make_json_response(order.goboxful_portal_progress())
