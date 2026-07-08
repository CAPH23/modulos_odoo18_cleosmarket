/** @odoo-module **/

import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

/*
 * Super Tienda Cleo - datos extra para el recibo nativo de POS.
 * Este patch afecta el botón POS -> Pedidos -> Pagados -> Imprimir recibo,
 * porque ese flujo usa el OrderReceipt del frontend del Punto de Venta.
 */
patch(PosOrder.prototype, {
    export_for_printing(baseUrl, headerData) {
        const result = super.export_for_printing(...arguments);

        const sortedLines = this.getSortedOrderlines ? this.getSortedOrderlines() : [];
        if (Array.isArray(result.orderlines)) {
            result.orderlines = result.orderlines.map((lineData, index) => {
                const orderLine = sortedLines[index];
                const product = orderLine && orderLine.get_product ? orderLine.get_product() : null;
                return {
                    ...lineData,
                    cleo_product_id: product && product.id ? product.id : false,
                    cleo_product_image_url: product && product.id ? `/web/image/product.product/${product.id}/image_128` : false,
                    cleo_product_name: lineData.productName || (product && product.display_name) || "Producto",
                };
            });
        }

        const company = this.company || {};
        result.cleo_company_logo_url = company.id ? `/web/image/res.company/${company.id}/logo` : false;
        result.cleo_company_name = "Super Tienda Cleo";
        result.cleo_company_address = "Carretera a Planes de Renderos Km 6 1/2, San Salvador, El Salvador";
        result.cleo_company_email = "supertiendacleo25@gmail.com";
        result.cleo_company_phone = "+503 6835-4506";
        result.cleo_receipt_title = "Ticket de Compra";
        result.cleo_paid_label = this.finalized ? "PAGADO" : "PENDIENTE";
        result.cleo_state_label = this.finalized ? "EN PREPARACION" : "EN PROCESO";
        result.cleo_order_origin = "Punto de venta";
        result.cleo_legal_note = "Este documento es un comprobante informativo de compra. No constituye factura fiscal ni comprobante de credito fiscal.";
        result.cleo_social_footer = "Facebook | Instagram | WhatsApp | @supertiendacleo";

        return result;
    },
});
