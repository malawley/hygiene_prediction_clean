FROM debian:bookworm-slim

WORKDIR /app

# Install debugging tools
RUN apt-get update && apt-get install -y curl ca-certificates && rm -rf /var/lib/apt/lists/*

# Copy and run
COPY build/trigger /trigger

EXPOSE 8080
CMD ["/trigger"]

