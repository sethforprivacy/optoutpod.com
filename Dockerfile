# nginx:alpine (multi-arch manifest digest pinned)
FROM nginx:alpine@sha256:0e5caf3555a79db2f1624c61fb1e585c4298a26384fea83f3e5108e451c1eb2c

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
