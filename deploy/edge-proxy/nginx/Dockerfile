FROM nginx:1.27-alpine@sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10

COPY *.template *.conf /etc/nginx/edge/
COPY docker-entrypoint.sh /usr/local/bin/edge-entrypoint
COPY reload.sh /usr/local/bin/edge-reload

RUN chmod 755 /usr/local/bin/edge-entrypoint /usr/local/bin/edge-reload

ENTRYPOINT ["/usr/local/bin/edge-entrypoint"]
CMD ["nginx", "-g", "daemon off;"]
