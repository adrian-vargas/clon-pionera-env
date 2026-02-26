# NIVEL 10 - Configuración del Portal Público

## Propósito

Este nivel valida que el Portal Público puede ser inicializado funcionalmente de forma automatizada sin intervención manual en el panel de administración de strapi.

Se demuestra que:
- El backend Strapi puede inicializarse programáticamente.
- El contenido mínimo obligatorio del Portal se crea automáticamente.
- Los permisos del rol `Public` se configuran sin uso del dashboard.
- El menú público requerido por el frontend existe.
- La API pública responde correctamente (`200 OK`).
- El frontend renderiza sin errores críticos de autorización.

## Ruta
``` text
pionera-env/
``` 

> **Precondiciones técnicas:**
> - El Nivel 9 debe haberse completado con éxito.
> - Todos los pods del Portal deben estar en estado `Running`.
> - El Ingress debe responder correctamente.
> - `minikube tunnel` debe estar activo en entorno WSL2 + Docker driver.

Verificación previa:

``` bash
kubectl get pods -n demo
curl -I http://demo.dev.ds.inesdata.upm
curl -I http://backend-demo.dev.ds.inesdata.upm/admin
```

Todos los servicios deben responder con `200 OK`.

## Ejecutar `portal-setup.py` (bootstrap funcional)

``` bash
python3 adapters/inesdata/integration/auth/auth-bootstrap.py
python3 adapters/inesdata/portal/portal-setup.py # Esperar algunos minutos (timeout de 300s)
```

El script ejecuta las siguientes acciones:

1. Espera activa hasta que el backend Strapi esté disponible.
2. Autenticación programática del administrador.
3. Generación automática de un API Token con acceso completo.
4. Generación dinámica de imágenes placeholder requeridas por el esquema.
5. Generación automàtica y subida de imágenes vía `/api/upload`.
6. Creación del Single Type `Landing Page` con todos sus componentes obligatorios.
7. Publicación automática del contenido (`publishedAt`).
8. Configuración automática del rol `Public`.
9. Creación idempotente del menú `public-portal-menu`.

No se requiere intervención manual en el panel de administración de Strapi.

### Verificación

```json
curl http://backend-demo.dev.ds.inesdata.upm/api/landing-page
curl "http://backend-demo.dev.ds.inesdata.upm/api/menus?filters%5Bslug%5D%5B%24eq%5D=public-portal-menu"
curl -X POST http://backend-demo.dev.ds.inesdata.upm/api/get-federated-catalog
```

**Ejemplo de salida esperada**
```text
$ python3 adapters/inesdata/portal/portal-setup.py
Portal bootstrap completed successfully.

$ curl http://backend-demo.dev.ds.inesdata.upm/api/landing-page
{
    "data": {
        "id": 1,
        "attributes": {
            "Title": "INESData Dataspace",
            "createdAt": "2026-02-19T19:59:43.512Z",
            "updatedAt": "2026-02-19T21:26:51.999Z",
            "publishedAt": "2026-02-19T21:26:51.954Z",
            "locale": "en"
        }
    },
    "meta": {}
}

$ curl "http://backend-demo.dev.ds.inesdata.upm/api/menus?filters%5Bslug%5D%5B%24eq%5D=public-portal-menu"
{
    "data": [
        {
            "id": 1,
            "attributes": {
                "title": "public-portal-menu",
                "slug": "public-portal-menu",
                "createdAt": "2026-02-19T20:28:47.321Z",
                "updatedAt": "2026-02-19T20:28:47.321Z"
            }
        }
    ],
    "meta": {
        "page": 1,
        "pageSize": 25,
        "pageCount": 1,
        "total": 1
    }
}

# Error esperado a solucionar en nivel 11 (no hay catálogo en el conector hasta este nivel):
$ curl -X POST http://backend-demo.dev.ds.inesdata.upm/api/get-federated-catalog
{   
    "message": "Error fetching federated catalog!",
    "details": "Failed to get access token"
}
```

Al acceder al frontend: http://demo.dev.ds.inesdata.upm el frontend carga correctamente y solo aparecen estos errores visuales esperados a resolver en nivel 11:
```text
- Error
  Error fetching federated catalog!
- Error
  Ha ocurrido un error procesando la operación
- Error
  Ha ocurrido un error procesando la operación
- Error
  Error fetching federated catalog!
```

## Criterios de aceptación
- La Landing Page existe y está publicada.
- El rol `Public` tiene permisos configurados automáticamente.
- El menú `public-portal-menu` existe.
- Los endpoints públicos responden con `200 OK`.
---
⬅️ [Nivel anterior: Nivel 9 - Despliegue del Portal Público](../nivel-9/README.md) </br>
➡️ [Siguiente nivel: Nivel 11 - Configuración del Connector](../nivel-11/README.md)</br>
🏠 [Volver al README principal](/README.md)

