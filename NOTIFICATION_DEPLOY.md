# Notification WebSocket Deployment

## Windows desktop notifications
- Production access must use an HTTPS domain. Plain LAN IP addresses over HTTP cannot request browser notification permission.
- For LAN deployment, point internal DNS at the LAN server and generate the Nginx config from `deploy/nginx-https.conf.template`.
- Users enable desktop notifications from the notification bell. Browser and Windows notification permissions remain under each user's control.
- This phase uses the existing WebSocket connection, so the page must remain open or minimized.

## Nginx
- Use `deploy/nginx-https.conf.template` for LAN desktop notifications. The repo `nginx.conf` and `frontend/nginx.conf` remain HTTP-only development/container defaults.
- Render the template with the real domain and trusted certificate paths as described in `局域网部署说明.md`.
- `/api/notifications/ws` must be proxied separately from generic `/api/` so the path is preserved and websocket timeouts can be increased.
- After updating the config, run `sudo nginx -t && sudo systemctl reload nginx`.

## Backend container
- Rebuild the backend image after this change because the `uvicorn` command now enables proxy headers.
- Recommended command: `docker-compose up -d --build backend`.

## Smoke checks
- Open the app, log in, then check browser DevTools Network for a `101 Switching Protocols` response on `/api/notifications/ws`.
- Trigger a workflow assignment or rollback and confirm a websocket frame is received.
- If the socket closes after about 60 seconds, the new Nginx config was not applied.
