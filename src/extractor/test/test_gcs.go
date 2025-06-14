package main

import (
	"context"
	"fmt"

	"cloud.google.com/go/storage"
)

func main() {
	ctx := context.Background()
	client, err := storage.NewClient(ctx)
	if err != nil {
		fmt.Println("❌ Failed to create GCS client:", err)
		return
	}
	defer client.Close()

	bucket := "raw-inspection-data-434"
	_, err = client.Bucket(bucket).Attrs(ctx)
	if err != nil {
		fmt.Println("❌ Could not access bucket:", err)
		return
	}

	fmt.Println("✅ Successfully connected to GCS bucket:", bucket)
}

