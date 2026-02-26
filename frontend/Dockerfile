# Frontend Dockerfile
FROM node:20-alpine

WORKDIR /app

# Build args for Next.js public env vars
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy application
COPY . .

# Build Next.js app
RUN npm run build

# Copy static assets into standalone output
RUN cp -r .next/static .next/standalone/.next/static
RUN cp -r public .next/standalone/public 2>/dev/null || true

# Expose port
EXPOSE 3000

# Run standalone server
CMD ["node", ".next/standalone/server.js"]

