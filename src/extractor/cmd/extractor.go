package main

import (
	"bytes"
	"configure"
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

var triggerURL string

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

func RunExtractor(date string, maxOffset int, triggerURL string) error {
	log.Println("➡️ RunExtractor started")

	// Notify trigger of extractor start
	startPayload := map[string]any{
		"event":     "extractor_started",
		"date":      date,
		"timestamp": time.Now().Format(time.RFC3339),
		"origin":    "extractor",
	}
	startBody, _ := json.Marshal(startPayload)

	_, err := http.Post(triggerURL, "application/json", bytes.NewBuffer(startBody))
	if err != nil {
		log.Printf("⚠️ Failed to notify trigger of extractor start: %v", err)
	} else {
		log.Printf("📤 Notified trigger: extractor_started")
	}

	startTime := time.Now()

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
	initialOffset := offset

	var files []string

	// 5. Begin fetch loop
	for {
		url := fmt.Sprintf("https://data.cityofchicago.org/resource/qizy-d2wf.json?$limit=%d&$offset=%d", chunkSize, offset)
		objectName := fmt.Sprintf("%s/offset_%d.json", folder, offset)

		log.Println("🌐 Fetching:", url)
		raw, err := fetchData(url)
		if err != nil {
			log.Println("❌ Fetch error:", err)
			break
		}
		if len(raw) < 100 {
			log.Println("✅ No more data to fetch.")
			break
		}

		// Parse JSON array
		var records []map[string]interface{}
		if err := json.Unmarshal(raw, &records); err != nil {
			log.Println("❌ Failed to parse JSON array:", err)
			break
		}

		// Convert to NDJSON
		var ndjsonBuf bytes.Buffer
		encoder := json.NewEncoder(&ndjsonBuf)
		for _, record := range records {
			if err := encoder.Encode(record); err != nil {
				log.Println("❌ Failed to encode NDJSON:", err)
				break
			}
		}

		// Save to GCS
		err = storageClient.SaveObject(bucket, objectName, ndjsonBuf.Bytes())
		if err != nil {
			log.Println("❌ Failed to save to GCS:", err)
			break
		}

		files = append(files, filepath.Base(objectName))
		offset += chunkSize
		storageClient.WriteCheckpoint(bucket, checkpointPath, offset)

		if maxOffset > 0 && offset >= initialOffset+maxOffset {
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

	// Compute Duration
	duration := time.Since(startTime).Seconds()

	// Notify trigger of completion
	completionPayload := map[string]any{
		"event":      "extractor_completed",
		"date":       date,
		"max_offset": maxOffset,
		"origin":     "extractor",
		"duration":   fmt.Sprintf("%.3f", duration),
	}
	completionBody, _ := json.Marshal(completionPayload)

	resp, err := http.Post(triggerURL, "application/json", bytes.NewBuffer(completionBody))
	if err != nil {
		log.Printf("❌ Failed to notify trigger: %v", err)
	} else {
		log.Printf("📤 Trigger notified: %s", resp.Status)
		resp.Body.Close()
	}

	log.Println("✅ RunExtractor completed")
	return nil
}

func handleExtract(w http.ResponseWriter, r *http.Request, triggerURL string) {
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
		err := RunExtractor(input.Date, input.MaxOffset, triggerURL)
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

	// Load trigger URL from services.json
	configPath := os.Getenv("SERVICE_CONFIG_PATH")
	if configPath == "" {
		configPath = "/services.json"
	}
	cfg, err := configure.LoadServiceConfig(configPath)
	if err != nil {
		log.Fatal("❌ Failed to load service config:", err)
	}
	triggerURL = cfg.Trigger.URL
	log.Printf("🔗 Trigger service URL: %s\n", triggerURL)

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
		http.HandleFunc("/extract", func(w http.ResponseWriter, r *http.Request) {
			handleExtract(w, r, triggerURL)
		})
		log.Fatal(http.ListenAndServe(":8080", nil))
		return
	}

	// ✅ CLI mode
	log.Println("🧪 Extractor running in CLI mode")
	maxOffset := flag.Int("max_offset", -1, "Optional: maximum offset to fetch for testing")
	flag.Parse()

	today := time.Now().Format("2006-01-02")
	err = RunExtractor(today, *maxOffset, triggerURL)
	if err != nil {
		log.Println("❌ Extractor failed:", err)
	}
}
