# === Stage 1: Build Go app ===

FROM golang:1.23 as builder 


WORKDIR /src

COPY . .

RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o /app/extractor ./cmd/extractor.go

# === Stage 2: Minimal runtime image ===
FROM gcr.io/distroless/base-debian12

WORKDIR /

COPY --from=builder /app/extractor /extractor

EXPOSE 8080
CMD ["/extractor"]
