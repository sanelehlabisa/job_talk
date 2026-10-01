FROM nginx:1.27-alpine@sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10

COPY bootstrap.conf.template /etc/nginx/jobtalk/bootstrap.conf.template
COPY production.conf.template /etc/nginx/jobtalk/production.conf.template
COPY docker-entrypoint.sh /usr/local/bin/jobtalk-nginx-entrypoint

RUN chmod 755 /usr/local/bin/jobtalk-nginx-entrypoint

ENTRYPOINT ["/usr/local/bin/jobtalk-nginx-entrypoint"]
CMD ["nginx", "-g", "daemon off;"]
