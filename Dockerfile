# nginx:alpine (multi-arch manifest digest pinned)
FROM nginx:alpine@sha256:72ba65eb42c10344912a84ff42408db7d34f2feb642204570ab8fc5ffd29f1d3

# Upgrade base image
RUN set -ex && apk --update --no-cache upgrade

# Copy clearnet static files
COPY public /usr/share/nginx/html/public

# Copy Tor static files
COPY tor /usr/share/nginx/html/tor

# Delete default nginx conf file
RUN rm /etc/nginx/conf.d/default.conf

# Copy custom nginx.conf file
COPY nginx.conf /etc/nginx/nginx.conf

HEALTHCHECK CMD wget -qO- --header "Host: optoutpod.com" http://127.0.0.1/ || exit 1

EXPOSE 80 443

# NOTE: Running as USER nginx was considered but intentionally deferred. The
# container binds the privileged ports 80/443; a non-root master process would
# fail to open those listeners without CAP_NET_BIND_SERVICE. Worker processes
# already run unprivileged as `user nginx;` in nginx.conf.
