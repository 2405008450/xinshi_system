# Notification WebSocket Deployment

## Nginx
- Use the repo `nginx.conf` for host deployment, or `frontend/nginx.conf` for containerized frontend.
- `/api/notifications/ws` must be proxied separately from generic `/api/` so the path is preserved and websocket timeouts can be increased.
- After updating the config, run `sudo nginx -t && sudo systemctl reload nginx`.

## Backend container
- Rebuild the backend image after this change because the `uvicorn` command now enables proxy headers.
- Recommended command: `docker-compose up -d --build backend`.

## Smoke checks
- Open the app, log in, then check browser DevTools Network for a `101 Switching Protocols` response on `/api/notifications/ws`.
- Trigger a workflow assignment or rollback and confirm a websocket frame is received.
- If the socket closes after about 60 seconds, the new Nginx config was not applied.
