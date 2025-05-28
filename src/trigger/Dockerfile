# Stage 1: Build the Go binary
FROM golang:1.22.3-alpine AS builder
WORKDIR /app
COPY . .
RUN go build -o trigger ./cmd/trigger.go


# Stage 2: Minimal final image
FROM debian:bookworm-slim
WORKDIR /app
RUN apt-get update && apt-get install -y curl ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/trigger /trigger

EXPOSE 8080
CMD ["/trigger"]

