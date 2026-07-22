# Configuración

## 1. Crear la cuenta por compañía

Inventario → Boxful → Configuración.

Para cada compañía configure:

- Modo: comenzar con **Simulado**.
- URL API.
- Correo y contraseña Boxful.
- Responsable interno.
- Dirección, departamento, municipio, referencia, teléfono y coordenadas.
- Horario y zona horaria.
- Dimensiones de respaldo para la caja.

## 2. Sincronizar ubicaciones

1. Presione **Probar conexión**.
2. Presione **Sincronizar ubicaciones**.
3. Revise Inventario → Boxful → Ciudades y mapeos.
4. Confirme que cada ciudad usada por clientes tenga mapeado el Municipio de Odoo.

El Distrito continúa almacenado en el campo de texto `city` de tu formulario actual; el módulo
no instala `base_address_city` ni cambia ese comportamiento.

## 3. Sincronizar la dirección de recolección

Presione **Sincronizar dirección**. El registro guardará el `recolectionAddressId` devuelto por Boxful.

## 4. Crear el método de entrega

Presione **Crear/Abrir método Boxful** desde la cuenta. Revise:

- Compañía.
- Producto de envío.
- Publicación en sitio web.
- Países o estados permitidos, si se usan filtros estándar.
- Solo couriers del mismo día.

El nivel de integración queda obligado a **Obtener tarifa**, para evitar que validar la transferencia cree automáticamente una guía.

## 5. Productos y categorías

- Peso: campo estándar `weight`, configurado en libras en esta instalación.
- Volumen: campo estándar `volume`, configurado en m³.
- Ancho/largo/alto: centímetros.
- Fragilidad: marque el campo Boxful.

El hook de instalación marca las categorías cuyo nombre contiene `PRODUCTOS CONGELADOS`. Revise manualmente la categoría y sus padres.

## 6. Webhook

1. Genere una clave.
2. Verifique la URL pública.
3. Presione **Registrar webhook**.
4. Compruebe que Nginx permita `POST` a `/goboxful/webhook/<company_id>`.

La URL incluye `?db=<base>` porque el servidor usa un `dbfilter` que puede coincidir con más de una base.

## 7. Flujo operativo

1. Cliente elige Boxful en checkout.
2. Odoo muestra la tarifa del courier same-day más económico.
3. Se confirma el pedido.
4. En la transferencia, el encargado abre la pestaña Boxful.
5. Cotiza o revisa alternativas.
6. Puede seleccionar otro courier del mismo día.
7. Presiona **Crear envío Boxful**.
8. Odoo guarda guía, tracking y etiqueta.

## 8. Producción

Cambie a producción solo después de confirmar con Boxful:

- Credenciales productivas.
- Unidades de peso y dimensiones.
- Comportamiento del secreto del webhook.
- Cobros y recolecciones generados por `POST /shipment`.
- Procedimiento de cancelación.
