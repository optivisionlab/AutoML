FROM node:26-alpine

WORKDIR /app

RUN apk add --no-cache libc6-compat

# Copy package descriptors for layer caching
COPY package.json package-lock.json ./
COPY packages/domain/package.json ./packages/domain/
COPY packages/api/package.json ./packages/api/

RUN npm install --legacy-peer-deps

# Copy source code
COPY . .

ENV NODE_ENV=development
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

EXPOSE 3000

CMD ["npm", "run", "build"]
