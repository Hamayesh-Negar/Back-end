FROM nginx:1.25-alpine

RUN rm /etc/nginx/conf.d/default.conf

COPY nginx.conf /etc/nginx/nginx.conf

RUN mkdir -p /app/staticfiles
RUN mkdir -p /app/media
RUN mkdir -p /etc/nginx/certs

EXPOSE 80 443
