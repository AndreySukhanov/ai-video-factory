# Frontend Dockerfile
FROM node:20-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy application
COPY . .

# Expose port
EXPOSE 3000

# Run dev server with host binding for Docker
CMD ["npm", "run", "dev", "--", "-H", "0.0.0.0"]

