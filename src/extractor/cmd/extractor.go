package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"math/rand/v2"
	"net/http"
	"os"
	"path/filepath"
	"time"

	"cloud.google.com/go/bigquery"
	"cloud.google.com/go/storage"
	"github.com/joho/godotenv"
)

var triggerURL string
var shutdownRequested = false

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
		return s.Client.Bucket(bucketName).Create(s.Ctx, "hygiene-prediction-434", &storage.BucketAttrs{Location: "US"})
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

	var checkpoint struct{ LastOffset int }
	if err := json.NewDecoder(reader).Decode(&checkpoint); err != nil {
		log.Println("Failed to parse checkpoint — starting from offset 0")
		return 0, nil
	}
	return checkpoint.LastOffset, nil
}

func (s *GCSStorage) WriteCheckpoint(bucket, path string, offset int) error {
	data, _ := json.MarshalIndent(map[string]int{"last_offset": offset}, "", "  ")
	return s.SaveObject(bucket, path, data)
}

func writeChunkMetrics(ctx context.Context, bqClient *bigquery.Client, datasetID, tableID string, offset int, metrics map[string]interface{}) {
	metrics["timestamp"] = time.Now()
	metrics["offset"] = offset

	log.Printf("📊 chunk_metrics: %+v", metrics)

	// Define a struct to match the BigQuery table schema
	type ChunkMetric struct {
		Offset               int       `bigquery:"offset"`
		RowsExtracted        int       `bigquery:"rows_extracted"`
		RowsDropped          int       `bigquery:"rows_dropped"`
		ChunkDurationSeconds float64   `bigquery:"chunk_duration_seconds"`
		DelayApplied         bool      `bigquery:"delay_applied"`
		FetchSkipped         bool      `bigquery:"fetch_skipped"`
		GCSWriteSkipped      bool      `bigquery:"gcs_write_skipped"`
		Timestamp            time.Time `bigquery:"timestamp"`
	}

	// Safely extract timestamp
	timestampVal, ok := metrics["timestamp"].(time.Time)
	if !ok {
		log.Printf("⚠️ Invalid timestamp format in metrics map")
		timestampVal = time.Now()
	}

	row := ChunkMetric{
		Offset:               metrics["offset"].(int),
		RowsExtracted:        metrics["rows_extracted"].(int),
		RowsDropped:          metrics["rows_dropped"].(int),
		ChunkDurationSeconds: metrics["chunk_duration_seconds"].(float64),
		DelayApplied:         metrics["delay_applied"].(bool),
		FetchSkipped:         metrics["fetch_skipped"].(bool),
		GCSWriteSkipped:      metrics["gcs_write_skipped"].(bool),
		Timestamp:            timestampVal,
	}

	inserter := bqClient.Dataset(datasetID).Table(tableID).Inserter()
	if err := inserter.Put(ctx, row); err != nil {
		log.Printf("❌ Failed to insert metrics into BigQuery: %v", err)
	} else {
		log.Printf("✅ Chunk metrics inserted into BigQuery: offset=%d", offset)
	}
}

func RunExtractor(date string, maxOffset int, triggerURL string, bqClient *bigquery.Client,
	apiErrorProb, gcsErrorProb, rowDropProb, delayProb float64) error {

	log.Println("➡️ RunExtractor started")
	log.Printf("🔧 Config: api=%.3f gcs=%.3f drop=%.3f delay=%.3f",
		apiErrorProb, gcsErrorProb, rowDropProb, delayProb)

	startPayload := map[string]any{
		"event":     "extractor_started",
		"date":      date,
		"timestamp": time.Now().Format(time.RFC3339),
		"origin":    "extractor",
	}
	startBody, _ := json.Marshal(startPayload)
	_, _ = http.Post(triggerURL, "application/json", bytes.NewBuffer(startBody))

	startTime := time.Now()

	storageClient, err := NewGCSStorage()
	if err != nil {
		log.Println("❌ Failed to create GCS client:", err)
		return err
	}
	ctx := storageClient.Ctx

	bucketName := os.Getenv("BUCKET_NAME")
	if bucketName == "" {
		log.Println("❌ BUCKET_NAME environment variable not set")
		return fmt.Errorf("BUCKET_NAME not set")
	}

	if err := storageClient.EnsureBucketExists(bucketName); err != nil {
		log.Println("❌ Bucket check failed:", err)
		return err
	}

	if date == "" {
		date = time.Now().Format("2006-01-02")
	}
	log.Printf("📅 Processing date: %s\n", date)

	chunkSize := 1000
	folder := fmt.Sprintf("raw-data/%s", date)
	checkpointPath := "last_checkpoint.json"

	offset, _ := storageClient.ReadCheckpoint(bucketName, checkpointPath)
	initialOffset := offset

	var files []string

	for {
		url := fmt.Sprintf("https://data.cityofchicago.org/resource/qizy-d2wf.json?$limit=%d&$offset=%d", chunkSize, offset)
		objectName := fmt.Sprintf("%s/offset_%d.json", folder, offset)
		chunkStart := time.Now()
		delayApplied := false
		rowsDropped := 0

		if rand.Float64() < apiErrorProb {
			log.Printf("❌ simulated_fetch_error: skipping chunk at offset %d", offset)
			writeChunkMetrics(ctx, bqClient, "PipelineMonitoring", "chunk_metrics", offset, map[string]interface{}{
				"fetch_skipped":          true,
				"gcs_write_skipped":      false,
				"rows_extracted":         0,
				"rows_dropped":           0,
				"chunk_duration_seconds": time.Since(chunkStart).Seconds(),
				"delay_applied":          false,
			})
			offset += chunkSize
			continue
		}

		log.Println("🌐 Fetching:", url)

		var raw []byte
		delay := 2 * time.Second

		for i := 0; i < 5; i++ {
			resp, err := http.Get(url)
			if err != nil {
				log.Printf("⚠️ Fetch attempt %d failed: %v", i+1, err)
			} else {
				defer resp.Body.Close()
				if resp.StatusCode == http.StatusOK {
					raw, err = io.ReadAll(resp.Body)
					break
				}
				log.Printf("⚠️ Fetch attempt %d failed: status %d", i+1, resp.StatusCode)
			}
			time.Sleep(delay)
			delay *= 2
		}

		if len(raw) < 100 {
			log.Println("✅ No more data to fetch.")
			break
		}

		var records []map[string]interface{}
		if err := json.Unmarshal(raw, &records); err != nil {
			log.Println("❌ Failed to parse JSON array:", err)
			break
		}

		var retained []map[string]interface{}
		log.Printf("🧪 rowDropProb just before row dropping is %.3f", rowDropProb)

		for _, r := range records {
			if rand.Float64() > rowDropProb {
				retained = append(retained, r)
			}
		}
		rowsDropped = len(records) - len(retained)
		log.Printf("🧪 Dropped %d out of %d rows", rowsDropped, len(records))
		records = retained

		var ndjsonBuf bytes.Buffer
		encoder := json.NewEncoder(&ndjsonBuf)
		for _, record := range records {
			if err := encoder.Encode(record); err != nil {
				log.Println("❌ Failed to encode NDJSON:", err)
				break
			}
		}

		if rand.Float64() < gcsErrorProb {
			log.Printf("❌ simulated_gcs_write_error: failed to save %s", objectName)
			writeChunkMetrics(ctx, bqClient, "PipelineMonitoring", "chunk_metrics", offset, map[string]interface{}{
				"fetch_skipped":          false,
				"gcs_write_skipped":      true,
				"rows_extracted":         len(records),
				"rows_dropped":           rowsDropped,
				"chunk_duration_seconds": time.Since(chunkStart).Seconds(),
				"delay_applied":          false,
			})
			offset += chunkSize
			continue
		}

		log.Printf("🧪 delayProb just before possible delays is %.3f", delayProb)
		if rand.Float64() < delayProb {
			log.Printf("🐢 simulated_processing_delay: sleeping 2 seconds")
			time.Sleep(2 * time.Second)
			delayApplied = true
		}

		err = storageClient.SaveObject(bucketName, objectName, ndjsonBuf.Bytes())
		if err != nil {
			log.Println("❌ Failed to save to GCS:", err)
			break
		}

		files = append(files, filepath.Base(objectName))

		writeChunkMetrics(ctx, bqClient, "PipelineMonitoring", "chunk_metrics", offset, map[string]interface{}{
			"fetch_skipped":          false,
			"gcs_write_skipped":      false,
			"rows_extracted":         len(records),
			"rows_dropped":           rowsDropped,
			"chunk_duration_seconds": time.Since(chunkStart).Seconds(),
			"delay_applied":          delayApplied,
		})

		offset += chunkSize
		storageClient.WriteCheckpoint(bucketName, checkpointPath, offset)

		if shutdownRequested {
			log.Println("🛑 Shutdown flag set — exiting after current chunk.")
			break
		}
		if maxOffset > 0 && offset >= initialOffset+maxOffset {
			log.Println("⏹️ Reached maxOffset — stopping early.")
			break
		}
	}

	manifest := map[string]interface{}{
		"date":            date,
		"files":           files,
		"upload_complete": true,
	}
	manifestData, _ := json.MarshalIndent(manifest, "", "  ")
	manifestName := fmt.Sprintf("raw-data/%s/_manifest.json", date)
	_ = storageClient.SaveObject(bucketName, manifestName, manifestData)
	log.Println("📦 Manifest written to:", manifestName)

	duration := time.Since(startTime).Seconds()

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

	log.Printf("✅ rows_extracted: %d", offset-initialOffset)
	log.Printf("📁 files_written_total: %d", len(files))
	log.Printf("⏱️ extraction_duration_seconds: %.3f", duration)
	log.Println("✅ RunExtractor completed")
	return nil
}

func handleExtract(w http.ResponseWriter, r *http.Request, triggerURL string, bqClient *bigquery.Client) {
	if r.Method != http.MethodPost {
		http.Error(w, "Only POST allowed", http.StatusMethodNotAllowed)
		return
	}

	var input struct {
		Date         string  `json:"date"`
		MaxOffset    int     `json:"max_offset"`
		APIErrorProb float64 `json:"api_error_prob"`
		GCSErrorProb float64 `json:"gcs_error_prob"`
		RowDropProb  float64 `json:"row_drop_prob"`
		DelayProb    float64 `json:"delay_prob"`
	}

	if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
		http.Error(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	// ✅ Log the incoming probabilities here (outside the goroutine)
	log.Printf("🧪 Incoming: api=%.3f gcs=%.3f drop=%.3f delay=%.3f",
		input.APIErrorProb, input.GCSErrorProb, input.RowDropProb, input.DelayProb)

	go func() {
		log.Printf("Forwarding: api=%.3f gcs=%.3f drop=%.3f delay=%.3f",
			input.APIErrorProb, input.GCSErrorProb, input.RowDropProb, input.DelayProb)
		err := RunExtractor(input.Date, input.MaxOffset, triggerURL, bqClient,
			input.APIErrorProb, input.GCSErrorProb, input.RowDropProb, input.DelayProb)
		if err != nil {
			log.Println("❌ Extractor failed via HTTP:", err)
		}
	}()

	w.WriteHeader(http.StatusOK)
	w.Write([]byte("Extractor started"))
}

func main() {
	log.Println("📍 Extractor starting main()")

	_ = godotenv.Load()

	// Setup context with timeout for BQ client creation
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	bqClient, err := bigquery.NewClient(ctx, "hygiene-prediction-434")
	if err != nil {
		log.Fatalf("❌ Failed to create BigQuery client: %v", err)
	}

	triggerURL = os.Getenv("TRIGGER_URL")
	if triggerURL == "" {
		log.Fatal("❌ TRIGGER_URL environment variable not set")
	}
	log.Printf("🔗 Trigger service URL: %s\n", triggerURL)

	log.SetOutput(os.Stdout)

	// Optional local dev logging to file
	// logFile, err := os.OpenFile("src/logs/extractor.log", os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0666)
	// if err == nil {
	//     log.SetOutput(io.MultiWriter(os.Stdout, logFile))
	//     defer logFile.Close()
	// } else {
	//     log.SetOutput(os.Stdout)
	//     log.Println("⚠️ Could not open log file — using stdout only:", err)
	// }

	http.HandleFunc("/extract", func(w http.ResponseWriter, r *http.Request) {
		handleExtract(w, r, triggerURL, bqClient)
	})

	http.HandleFunc("/shutdown", func(w http.ResponseWriter, r *http.Request) {
		log.Println("🛑 Shutdown requested — will exit after current fetch.")
		shutdownRequested = true
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("Shutdown initiated."))
	})

	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"status":"ok"}`))
	})

	log.Fatal(http.ListenAndServe(":8080", nil))
}
