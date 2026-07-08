Payment Provider: Wompi El Salvador v2
======================================

Módulo de integración de Wompi El Salvador para Odoo 18 Community.

Funcionalidades principales
---------------------------

* Creación de enlace de pago Wompi desde el checkout de Odoo.
* Redirección del cliente hacia Wompi.
* Validación del retorno mediante HMAC.
* Webhook con validación HMAC sobre el cuerpo completo.
* Fallback opcional por API ``TransaccionCompra`` cuando un proxy elimina el header ``wompi_hash``.
* Consulta opcional de capacidades del comercio mediante ``/Aplicativo``.
* Configuración de tarjeta, puntos Banco Agrícola, cuotas, Bitcoin y QuickPay.
* Configuración de límites de uso del enlace.
* Configuración de descripción, imagen, título y correos de notificación enviados a Wompi.
* Confirmación automática de la venta cuando Wompi confirma el pago.
* Registro de referencias Wompi en la transacción de pago.
* Logs de depuración configurables.

Notas
-----

Este módulo usa la arquitectura nativa de Odoo 18: ``payment.provider``,
``payment.transaction`` y controladores HTTP. No copia código PHP del plugin de
WooCommerce; solo replica funcionalidades relevantes de forma nativa en Odoo.

Imágenes homologadas con plugin WooCommerce Wompi
-------------------------------------------------
Esta versión incluye las imágenes del plugin WooCommerce Wompi en posiciones equivalentes dentro de Odoo:

* ``static/src/img/wompi.png``: icono del proveedor de pago, equivalente a ``$this->icon`` en WooCommerce.
* ``static/src/img/wompi2.png`` / ``tarjeta_de_credito.png``: logos de tarjetas soportadas, usados únicamente en el método propio ``wompi_sv_card`` para no modificar el método global ``card`` de Odoo.
* ``static/src/img/banner-772x250.png``: banner público enviado en ``infoProducto.urlImagenProducto`` al crear el enlace de pago.
* ``static/description/icon.png``: icono del módulo en la lista de aplicaciones de Odoo.

También se conservan alias de compatibilidad:

* ``static/src/img/wompi_logo.png``
* ``static/src/img/tarjeta_de_credito.png``
* ``static/src/img/wompi_payment_banner.png``
