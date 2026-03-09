# Build stage
FROM node:18-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# Production stage
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html

# Startup script that injects BACKEND_URL and PORT at runtime
RUN printf '#!/bin/sh\n\
LISTEN_PORT="${PORT:-80}"\n\
API_BACKEND="${BACKEND_URL:-http://backend:8000}"\n\
cat > /etc/nginx/conf.d/default.conf <<NGINXEOF\n\
server {\n\
    listen $LISTEN_PORT;\n\
    server_name _;\n\
    root /usr/share/nginx/html;\n\
    index index.html;\n\
    location / {\n\
        try_files \\$uri \\$uri/ /index.html;\n\
    }\n\
    location /api/ {\n\
        proxy_pass $API_BACKEND;\n\
        proxy_set_header Host \\$host;\n\
        proxy_set_header X-Real-IP \\$remote_addr;\n\
        proxy_set_header X-Forwarded-For \\$proxy_add_x_forwarded_for;\n\
        proxy_set_header X-Forwarded-Proto \\$scheme;\n\
        proxy_read_timeout 120s;\n\
    }\n\
    location /ws {\n\
        proxy_pass $API_BACKEND;\n\
        proxy_http_version 1.1;\n\
        proxy_set_header Upgrade \\$http_upgrade;\n\
        proxy_set_header Connection "upgrade";\n\
        proxy_set_header Host \\$host;\n\
    }\n\
    gzip on;\n\
    gzip_types text/plain text/css application/json application/javascript text/xml;\n\
    gzip_min_length 256;\n\
}\n\
NGINXEOF\n\
exec nginx -g "daemon off;"\n' > /start.sh && chmod +x /start.sh

EXPOSE 80
CMD ["/start.sh"]
