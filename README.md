# Raíz

Tienda y comunidad para huertos urbanos, construida con Flask, Flask-SQLAlchemy, Flask-Login, Jinja2, CSS, JavaScript nativo y Leaflet.

## Ejecutar

```bash
python -m pip install -r requirements.txt
flask --app app run --debug
```

La aplicación crea `database.db` y carga cinco semillas y tres cuentas demo al arrancar por primera vez. Para despliegues, configura `SECRET_KEY` con un valor secreto propio.

## Cuentas demo

Las tres cuentas comparten la contraseña `raizdemo`:

- `sofia@raiz.demo`
- `mateo@raiz.demo`
- `lucia@raiz.demo`

## Funciones

- Catálogo filtrable y kits Inicio, Recarga y Solo Semillas con precios calculados por variedad.
- Carrito guardado en la sesión y checkout que persiste pedidos para usuarios autenticados.
- Guías por cultivo en “Mis plantas”, con pasos marcables que se guardan en el navegador.
- Mapa de comunidad con ubicaciones y plantas compradas; los perfiles aparecen solo con consentimiento.

El checkout guarda el pedido, pero no procesa pagos. La base local se crea automáticamente y está excluida de Git.
