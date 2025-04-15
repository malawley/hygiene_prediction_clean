package main

import (
	"bytes"
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"time"

	"cloud.google.com/go/storage"
	"github.com/joho/godotenv"
)

// GCSStorage handles writing files to a GCS bucket
type GCSStorage struct {
	Client *storage.Client
	Ctx    context.Context
}

func NewGCSStorage() (*GCSStorage, error) {
	ctx := context.Background()
	client, err := storage.NewClient(ctx)
	if err != nil {
		return nil, err
	}
	return &GCSStorage{Client: client, Ctx: ctx}, nil
}

func (s *GCSStorage) EnsureBucketExists(bucketName string) error {
	_, err := s.Client.Bucket(bucketName).Attrs(s.Ctx)
	if err == storage.ErrBucketNotExist {
		log.Printf("Bucket %s does not exist. Creating...", bucketName)
		return s.Client.Bucket(bucketName).Create(s.Ctx, "hygiene-prediction", &storage.BucketAttrs{
			Location: "US",
		})
	}
	return err
}

func (s *GCSStorage) SaveObject(bucket, objectPath string, data []byte) error {
	writer := s.Client.Bucket(bucket).Object(objectPath).NewWriter(s.Ctx)
	writer.ContentType = "application/json"
	_, err := writer.Write(data)
	if err != nil {
		return err
	}
	return writer.Close()
}

func (s *GCSStorage) ReadCheckpoint(bucket, path string) (int, error) {
	reader, err := s.Client.Bucket(bucket).Object(path).NewReader(s.Ctx)
	if err != nil {
		log.Println("No checkpoint found — starting from offset 0")
		return 0, nil
	}
	defer reader.Close()

	var checkpoint struct {
		LastOffset int `json:"last_offset"`
	}
	err = json.NewDecoder(reader).Decode(&checkpoint)
	if err != nil {
		log.Println("Failed to parse checkpoint — starting from offset 0")
		return 0, nil
	}
	return checkpoint.LastOffset, nil
}

func (s *GCSStorage) WriteCheckpoint(bucket, path string, offset int) error {
	data, _ := json.MarshalIndent(map[string]int{"last_offset": offset}, "", "  ")
	return s.SaveObject(bucket, path, data)
}

func fetchData(url string) ([]byte, error) {
	resp, err := http.Get(url)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("unexpected status: %d", resp.StatusCode)
	}
	return io.ReadAll(resp.Body)
}

func RunExtractor(date string, maxOffset int) error {
	log.Println("➡️ RunExtractor started")

	// 1. Set up GCS client
	storageClient, err := NewGCSStorage()
	if err != nil {
		log.Println("❌ Failed to create GCS client:", err)
		return err
	}

	// 2. Ensure bucket exists
	bucket := os.Getenv("BUCKET_NAME")
	if bucket == "" {
		log.Println("❌ BUCKET_NAME environment variable not set")
		return fmt.Errorf("BUCKET_NAME not set")
	}

	if err := storageClient.EnsureBucketExists(bucket); err != nil {
		log.Println("❌ Bucket check failed:", err)
		return err
	}

	// 3. Use today's date if not provided
	if date == "" {
		date = time.Now().Format("2006-01-02")
	}
	log.Printf("📅 Processing date: %s\n", date)

	// 4. Prepare folder structure and checkpoint
	chunkSize := 1000
	folder := fmt.Sprintf("raw-data/%s", date)
	checkpointPath := "last_checkpoint.json"

	offset, _ := storageClient.ReadCheckpoint(bucket, checkpointPath)
	var files []string

	// 5. Begin fetch loop
	for {
		url := fmt.Sprintf("https://data.cityofchicago.org/resource/qizy-d2wf.json?$limit=%d&$offset=%d", chunkSize, offset)
		objectName := fmt.Sprintf("%s/offset_%d.json", folder, offset)

		log.Println("🌐 Fetching:", url)
		data, err := fetchData(url)
		if err != nil {
			log.Println("❌ Fetch error:", err)
			break
		}
		if len(data) < 100 {
			log.Println("✅ No more data to fetch.")
			break
		}

		err = storageClient.SaveObject(bucket, objectName, data)
		if err != nil {
			log.Println("❌ Failed to save to GCS:", err)
			break
		}

		files = append(files, filepath.Base(objectName))
		offset += chunkSize
		storageClient.WriteCheckpoint(bucket, checkpointPath, offset)

		if maxOffset > 0 && offset >= maxOffset {
			log.Println("⏹️ Reached maxOffset — stopping early.")
			break
		}
	}

	// 6. Write manifest to GCS
	manifest := map[string]interface{}{
		"date":            date,
		"files":           files,
		"upload_complete": true,
	}
	manifestData, _ := json.MarshalIndent(manifest, "", "  ")
	manifestName := fmt.Sprintf("%s/_manifest.json", folder)
	err = storageClient.SaveObject(bucket, manifestName, manifestData)
	if err != nil {
		log.Println("❌ Failed to write manifest:", err)
		return err
	}
	log.Println("📦 Manifest written to:", manifestName)

	// 7. Trigger Cleaner via HTTP POST
	cleanerURL := os.Getenv("CLEANER_URL")
	if cleanerURL == "" {
		log.Println("⚠️ CLEANER_URL not set — skipping cleaner trigger")
	} else {
		payload := map[string]string{"date": date}
		body, _ := json.Marshal(payload)

		resp, err := http.Post(cleanerURL, "application/json", bytes.NewBuffer(body))
		if err != nil {
			log.Println("❌ Failed to trigger cleaner:", err)
		} else {
			defer resp.Body.Close()
			log.Printf("✅ Cleaner triggered, status: %s\n", resp.Status)
		}
	}

	log.Println("✅ RunExtractor completed")
	return nil
}

func handleExtract(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Only POST allowed", http.StatusMethodNotAllowed)
		return
	}

	var input struct {
		Date      string `json:"date"`
		MaxOffset int    `json:"max_offset"` // ✅ Add support for limit
	}

	err := json.NewDecoder(r.Body).Decode(&input)
	if err != nil {
		http.Error(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	go func() {
		err := RunExtractor(input.Date, input.MaxOffset) // ✅ Pass maxOffset into extractor
		if err != nil {
			log.Println("❌ Extractor failed via HTTP:", err)
		}
	}()

	w.WriteHeader(http.StatusOK)
	w.Write([]byte("Extractor started"))
}

func main() {
	// ✅ Load environment variables from .env
	_ = godotenv.Load()

	// ✅ Set up logging (for both CLI and HTTP)
	_ = os.MkdirAll("src/logs", os.ModePerm)
	logFile, err := os.OpenFile("src/logs/extractor.log", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0666)
	if err == nil {
		log.SetOutput(io.MultiWriter(os.Stdout, logFile)) // 🪵 log to both terminal and file
	} else {
		log.SetOutput(os.Stdout)
		log.Println("⚠️ Could not open log file — using stdout only:", err)
	}
	defer logFile.Close()

	// ✅ HTTP mode
	if os.Getenv("HTTP_MODE") == "true" {
		log.Println("🚀 Starting Extractor in HTTP mode on :8080")
		http.HandleFunc("/extract", handleExtract)
		log.Fatal(http.ListenAndServe(":8080", nil))
		return
	}

	// ✅ CLI mode
	log.Println("🧪 Extractor running in CLI mode")
	maxOffset := flag.Int("max_offset", -1, "Optional: maximum offset to fetch for testing")
	flag.Parse()

	today := time.Now().Format("2006-01-02")
	err = RunExtractor(today, *maxOffset)
	if err != nil {
		log.Println("❌ Extractor failed:", err)
	}
}

// func main() {
// 	// Set up log file
// 	_ = os.MkdirAll("src/logs", os.ModePerm)
// 	logFile, err := os.OpenFile("src/logs/extractor.log", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0666)
// 	if err != nil {
// 		fmt.Println("❌ Failed to open log file:", err)
// 		return
// 	}
// 	defer logFile.Close()
// 	log.SetOutput(logFile)
// 	log.Println("Extractor started")

// 	// Parse optional max_offset flag
// 	maxOffset := flag.Int("max_offset", -1, "Optional: maximum offset to fetch for testing")
// 	flag.Parse()

// 	storageClient, err := NewGCSStorage()
// 	if err != nil {
// 		log.Println("Failed to create GCS client:", err)
// 		return
// 	}

// 	bucket := "raw-inspection-data"
// 	if err := storageClient.EnsureBucketExists(bucket); err != nil {
// 		log.Println("Bucket check failed:", err)
// 		return
// 	}

// 	chunkSize := 1000
// 	today := time.Now().Format("2006-01-02")
// 	folder := fmt.Sprintf("raw-data/%s", today)
// 	checkpointPath := "last_checkpoint.json"

// 	offset, _ := storageClient.ReadCheckpoint(bucket, checkpointPath)
// 	var files []string

// 	for {
// 		url := fmt.Sprintf("https://data.cityofchicago.org/resource/qizy-d2wf.json?$limit=%d&$offset=%d", chunkSize, offset)
// 		objectName := fmt.Sprintf("%s/offset_%d.json", folder, offset)

// 		log.Println("Fetching:", url)
// 		fmt.Println("🔄 Fetching:", url)

// 		data, err := fetchData(url)
// 		if err != nil {
// 			log.Println("Fetch error:", err)
// 			break
// 		}
// 		if len(data) < 100 {
// 			log.Println("No more data to fetch.")
// 			break
// 		}

// 		if err := storageClient.SaveObject(bucket, objectName, data); err != nil {
// 			log.Println("Failed to save to GCS:", err)
// 			break
// 		}

// 		files = append(files, filepath.Base(objectName))
// 		offset += chunkSize
// 		storageClient.WriteCheckpoint(bucket, checkpointPath, offset)

// 		if *maxOffset > 0 && offset >= *maxOffset {
// 			log.Println("Reached max_offset — ending early.")
// 			break
// 		}
// 	}

// 	// Write manifest
// 	manifest := map[string]interface{}{
// 		"date":            today,
// 		"files":           files,
// 		"upload_complete": true,
// 	}
// 	manifestData, _ := json.MarshalIndent(manifest, "", "  ")
// 	manifestName := fmt.Sprintf("%s/_manifest.json", folder)
// 	if err := storageClient.SaveObject(bucket, manifestName, manifestData); err != nil {
// 		log.Println("Failed to write manifest:", err)
// 	} else {
// 		log.Println("Manifest written to:", manifestName)
// 	}

// 	log.Println("Extractor finished")
// }
