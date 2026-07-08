# Cleo - Confirmación de Pedido Mejorada

Módulo para Odoo 18 Community que personaliza la página `/shop/confirmation` de Super Tienda Cleo.

## Funcionalidad

- Reemplaza visualmente la vista `website_sale.confirmation`.
- Muestra pedido confirmado, estado de preparación y resumen del pedido.
- Botones funcionales:
  - Volver al inicio → `/`
  - Continuar comprando → `/shop`
  - Ver mi pedido → URL de portal del pedido
  - Descargar comprobante → PDF de factura si existe factura publicada; si no existe, se oculta.
- No modifica lógica de pagos, contabilidad, inventario ni Wompi.

## Instalación

Copiar la carpeta `website_sale_confirmation_cleo` dentro de:

```bash
/opt/odoo18/odoo-extra-addons/
```

Actualizar la lista de aplicaciones o instalar por comando:

```bash
sudo -u odoo18 /opt/odoo18/odoo-venv/bin/python3 /opt/odoo18/odoo/odoo-bin -c /etc/odoo18.conf -d cleosmarket.com -i website_sale_confirmation_cleo --stop-after-init

sudo systemctl restart odoo18
```

Para actualizar:

```bash
sudo -u odoo18 /opt/odoo18/odoo-venv/bin/python3 /opt/odoo18/odoo/odoo-bin -c /etc/odoo18.conf -d cleosmarket.com -u website_sale_confirmation_cleo --stop-after-init

sudo systemctl restart odoo18
```


## 18.0.1.0.1
- Corrige XPath de instalación para Odoo 18: reemplaza el `t-call` de `website_sale.checkout_layout` en lugar de buscar `div#wrap` dentro de `website_sale.confirmation`.
- Ajusta importes calculados para renderizarse con `t-out` y widget monetario.
