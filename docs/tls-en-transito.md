# TLS en tránsito — despliegue v1 (C-13 task 1.3)

## Requisito
Todas las rutas expuestas por el reverse proxy/Compose deben usar HTTPS en
entornos de despliegue (no dev local). HTTP plano se rechaza fuera de dev.

## Stack
- `docker-compose.yml` expone `api` en el puerto 8000 sin TLS (dev local).
- En despliegue, un reverse proxy externo (nginx/traefik) termina TLS y
  reenvía a `api` sobre HTTP interno. El proxy es responsable de:
  - Certificado válido (Let's Encrypt o CA interna).
  - Redirección HTTP → HTTPS (HSTS opcional).
  - Solo puerto 443 expuesto; 80 redirige a 443.

## Excepción controlada en dev local
En `docker-compose.yml` (dev) no hay reverse proxy ni HTTPS. La excepción está
documentada y controlada: `cookie_secure` en `app/core/settings.py` devuelve
`False` cuando `FRONTEND_URL` empieza por `http://localhost` o
`http://127.`. El flag `ENVIRONMENT=dev` indica que TLS no es obligatorio.

## Verificación
- Despliegue: `GET http://<host>/api/health` debe responder 301/308 a
  `https://<host>/api/health`.
- Dev local: `http://localhost:8000/api/health` responde 200 (excepción
  documentada).

## Referencia
- `08_arquitectura_propuesta.md` §7 (cifrado en tránsito).
- `02_descripcion_general.md` §5 (cumplimiento mínimo v1).
