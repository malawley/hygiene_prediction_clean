# Use official Go base image
FROM golang:1.23 AS builder

# Set working directory
WORKDIR /app

# Copy go.mod and go.sum and download dependencies
COPY go.mod go.sum ./
RUN go mod download

# Copy the rest of the source code
COPY . .

# Build the Go binary
RUN go build -o extractor ./src/extractor/extractor.go

# Use a minimal base image for runtime
FROM gcr.io/distroless/base-debian12

# Set working directory inside container
WORKDIR /

# Copy the built binary from builder stage
COPY --from=builder /app/extractor /extractor

# Expose port for Cloud Run
EXPOSE 8080

# Run the binary
CMD ["/extractor"]
