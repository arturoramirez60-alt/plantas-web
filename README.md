# Raíz

Tienda y comunidad para huertos urbanos, construida con Flask, Flask-SQLAlchemy, Flask-Login, Jinja2, CSS, JavaScript y Leaflet.

## Ejecutar

```bash
python -m pip install -r requirements.txt
flask --app app run --debug
```

La aplicación crea `database.db` y carga cinco semillas, tres cuentas demo y cuatro huertos ficticios al arrancar por primera vez. Las tablas existentes no se eliminan; SQLAlchemy agrega las tablas de plantas y huertos. Para despliegues, configura `SECRET_KEY` con un valor secreto propio.
Puedes cambiar la ubicación de la base con `DATABASE_URL`; por defecto se usa SQLite local.

## Cuentas demo

Las tres cuentas comparten la contraseña `raizdemo`:

- `sofia@raiz.demo`
- `mateo@raiz.demo`
- `lucia@raiz.demo`

## Funciones

- Catálogo filtrable y kits Inicio, Recarga y Solo Semillas con precios calculados por variedad.
- Carrito guardado en la sesión y checkout que persiste pedidos para usuarios autenticados.
- Guías por cultivo en “Mis plantas”, con pasos marcables que se guardan en el navegador.
- Sesiones de usuario con Flask-Login, registro con contraseñas hash y pedidos persistidos en SQLite.
- Comunidad con perfiles de huertos, plantas relacionadas, fotos opcionales, filtros AJAX y un mapa 2D de México con Leaflet.
- Comentarios públicos dentro de cada perfil de huerto, con inicio de sesión, límite de longitud y moderación por el autor o el dueño.
- Los huertos solo aparecen con consentimiento; el mapa publica ubicaciones aproximadas generadas por ciudad y nunca expone correos, teléfonos o coordenadas introducidas por usuarios.
- Los formularios POST incluyen token CSRF. Las fotos se limitan a JPG, PNG o WebP de hasta 4 MB y se almacenan bajo `static/uploads/gardens/`.

El catálogo conserva los precios de referencia en la base, pero en modo de prueba (`DEMO_MODE=1`, valor predeterminado) todos los kits y pedidos son gratis. El checkout solo registra el pedido: no hay pasarela ni método de pago. Para volver a mostrar precios de referencia, configura `DEMO_MODE=0`.

## Probar la comunidad

1. Inicia sesión con cualquiera de las cuentas demo y la contraseña `raizdemo`.
2. Abre **Comunidad** y prueba los perfiles ficticios, filtros por planta, categoría, espacio, zona y disponibilidad.
3. Usa **Registra tu huerto** para guardar uno asociado a tu cuenta. Debes tener una compra registrada y solo puedes seleccionar semillas del catálogo que hayas comprado. Puedes dejar desactivada su aparición en el mapa y cambiar la visibilidad desde **Mis plantas**.
4. Las ubicaciones públicas se aproximan a partir de la ciudad y la zona; solo las ciudades con centro aproximado configurado pueden publicarse por ahora.

El mapa de la comunidad permite explorar México con Leaflet y mosaicos de OpenStreetMap.de, sin requerir una API key. Muestra los huertos publicados con ubicaciones aproximadas. Leaflet se carga desde jsDelivr y los mosaicos desde OpenStreetMap.de, por lo que se requiere conexión a internet. La capa de comunicación entre usuarios (mensajes, intercambio coordinado y notificaciones) queda para una fase posterior.
