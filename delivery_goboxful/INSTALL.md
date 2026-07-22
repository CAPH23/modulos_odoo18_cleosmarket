# Instalación

## 1. Probar primero en una base de staging

No instale la primera versión directamente en producción. Use una base que cumpla el `dbfilter`, por ejemplo:

```text
cleosmarket_boxful_dev
```

## 2. Copiar el módulo

```bash
sudo unzip delivery_goboxful_v1.0.0.zip -d /opt/odoo18/odoo-extra-addons/
sudo chown -R odoo18:odoo18 /opt/odoo18/odoo-extra-addons/delivery_goboxful
sudo find /opt/odoo18/odoo-extra-addons/delivery_goboxful -type d -exec chmod 755 {} \;
sudo find /opt/odoo18/odoo-extra-addons/delivery_goboxful -type f -exec chmod 644 {} \;
```

## 3. Instalar con el mismo Python del servicio

```bash
sudo -u odoo18 \
  /opt/odoo18/odoo-venv/bin/python3 \
  /opt/odoo18/odoo/odoo-bin \
  -c /etc/odoo18.conf \
  -d cleosmarket_boxful_dev \
  -i delivery_goboxful \
  --stop-after-init
```

Revise el log. Si la instalación termina correctamente:

```bash
sudo systemctl restart odoo18
sudo systemctl status odoo18 --no-pager
```

## 4. Actualizaciones posteriores

```bash
sudo -u odoo18 \
  /opt/odoo18/odoo-venv/bin/python3 \
  /opt/odoo18/odoo/odoo-bin \
  -c /etc/odoo18.conf \
  -d cleosmarket_boxful_dev \
  -u delivery_goboxful \
  --stop-after-init
```

## 5. No usar el Python global

El servicio Odoo usa:

```text
/opt/odoo18/odoo-venv/bin/python3
```

Ejecutar `odoo-bin` con `/usr/bin/python3` produce errores de dependencias como `No module named lxml` aunque el servicio esté funcionando correctamente.
