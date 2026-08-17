FROM node:20-alpine AS build

WORKDIR /app

ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

COPY package.json package-lock.json ./
RUN npm config set registry https://registry.npmjs.org/ \
    && npm ci \
    && npm install @rollup/rollup-linux-x64-musl@4.59.0 --no-save

COPY . .
ENV NODE_OPTIONS="--max-old-space-size=4096"
RUN npm run build

FROM nginx:1.27-alpine

COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
