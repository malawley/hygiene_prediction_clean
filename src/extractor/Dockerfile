# Use a minimal base image for runtime
FROM gcr.io/distroless/base-debian12

# Set working directory in container
WORKDIR /

# Copy the prebuilt binary and service config
COPY build/extractor /extractor
COPY services.json /services.json

# Expose port
EXPOSE 8080

# Run the binary
CMD ["/extractor"]
