Instalación
===========

1. Copiar la carpeta ``payment_wompi_sv`` en el ``addons_path`` de Odoo.
2. Actualizar la lista de aplicaciones.
3. Instalar o actualizar el módulo ``payment_wompi_sv``.
4. Configurar las credenciales del proveedor Wompi El Salvador.
5. Ejecutar ``Probar conexión OAuth`` y luego ``Actualizar capacidades Wompi``.
6. Habilitar el proveedor.

Comandos recomendados::

    sudo -u odoo18 /opt/odoo18/odoo-venv/bin/python3 /opt/odoo18/odoo/odoo-bin \
      -c /etc/odoo18.conf \
      -d cleosmarket.com \
      -u payment_wompi_sv \
      --stop-after-init

    sudo systemctl restart odoo18
