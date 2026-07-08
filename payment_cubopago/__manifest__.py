# -*- coding: utf-8 -*-
# Part of the CuboPago payment module.
# Copyright 2026 Carlos Palacios
# License OPL-1 (Odoo Proprietary License v1.0). See LICENSE file for full details.
{
    'name': 'CuboPago',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Payment Providers',
    'sequence': 350,
    'summary': 'Acepta pagos con CuboPago en Odoo mediante link de pago y '
               'webhook, con soporte de sandbox y producción.',
    'description': """
CuboPago - Proveedor de pago para Odoo 18
==========================================

Integra la pasarela de pago CuboPago con el comercio electrónico de Odoo 18
usando la arquitectura nativa de proveedores de pago (payment.provider /
payment.transaction).

Funcionalidades
---------------
* Creación automática del link de pago CuboPago desde el checkout de Odoo.
* Redirección segura del cliente a la pantalla de pago de CuboPago.
* Confirmación del pedido por webhook, con verificación obligatoria
  servidor-a-servidor contra el endpoint de transacciones (el webhook de
  CuboPago no incluye firma, por lo que cada notificación se valida vía API).
* Selector de entorno SANDBOX / PRODUCCIÓN con API Key y URL base configurables
  por entorno (ligado al modo de prueba del proveedor en Odoo).
* Envío opcional del detalle de productos (items) y datos del cliente.
* Soporte de meses sin intereses (monthlyInstallmentId).
* Manejo correcto del monto en centavos requerido por CuboPago.
* Registro de referencias de la transacción dentro de Odoo.
* Logs de depuración configurables.

Soporte
-------
Soporte de configuración y corrección de errores para clientes con licencia.
Contacto: ph03001gnu@yahoo.com
""",
    'author': 'Carlos Palacios',
    'maintainer': 'Carlos Palacios',
    'company': 'Carlos Palacios',
    'website': '',
    'support': 'ph03001gnu@yahoo.com',
    'depends': ['payment', 'website_sale'],
    'data': [
        'views/payment_cubopago_templates.xml',
        'views/payment_provider_views.xml',
        'data/payment_provider_data.xml',
        'data/payment_method_attach.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'payment_cubopago/static/src/scss/payment_cubopago.scss',
        ],
    },
    'images': ['static/description/banner.png'],
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'license': 'OPL-1',
    'price': 49.99,
    'currency': 'USD',
    'application': False,
    'installable': True,
}
