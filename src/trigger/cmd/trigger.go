package main

import (
	"app/configure"
	"bytes"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"time"
)

// Global service URLs loaded from services.json
var extractorURL string
var cleanerURL string
var loaderURL string
var loaderParquetURL string

// Place this at the top, after imports but before handleTrigger
func forwardToService(url, label string, payload map[string]string) {
	body, err := json.Marshal(payload)
	if err != nil {
		log.Printf("❌ Failed to marshal payload for %s: %v", label, err)
		return
	}

	resp, err := http.Post(url, "application/json", bytes.NewBuffer(body))
	if err != nil {
		log.Printf("❌ Failed to forward to %s (%s): %v", label, url, err)
		return
	}
	defer resp.Body.Close()

	respBody, _ := io.ReadAll(resp.Body)
	log.Printf("✅ Forwarded to %s | Status: %s | Response: %s", label, resp.Status, string(respBody))
}

func handleRun(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Only POST allowed", http.StatusMethodNotAllowed)
		return
	}

	var payload struct {
		Date         string  `json:"date"`
		MaxOffset    int     `json:"max_offset"`
		APIErrorProb float64 `json:"api_error_prob"`
		GCSErrorProb float64 `json:"gcs_error_prob"`
		RowDropProb  float64 `json:"row_drop_prob"`
		DelayProb    float64 `json:"delay_prob"`
	}

	if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
		log.Println("❌ Failed to decode /run payload:", err)
		http.Error(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	log.Printf("🧪 Raw struct payload: %+v", payload)
	log.Printf("🧪 Received payload: api=%v gcs=%v drop=%v delay=%v",
		payload.APIErrorProb, payload.GCSErrorProb, payload.RowDropProb, payload.DelayProb)
	log.Printf("🚀 HOWDY!")
	log.Printf("🚀 Pipeline run ONE started for date=%s with max_offset=%d", payload.Date, payload.MaxOffset)
	log.Printf("🚀 Pipeline run TWO started for date=%s with max_offset=%d with api=%v", payload.Date, payload.MaxOffset, payload.APIErrorProb)
	log.Printf("🧪 Raw struct payload: %+v", payload)
	log.Printf("🧪 Received payload: api=%v gcs=%v drop=%v delay=%v",
		payload.APIErrorProb, payload.GCSErrorProb, payload.RowDropProb, payload.DelayProb)

	data := map[string]interface{}{
		"date":           payload.Date,
		"max_offset":     payload.MaxOffset,
		"api_error_prob": payload.APIErrorProb,
		"gcs_error_prob": payload.GCSErrorProb,
		"row_drop_prob":  payload.RowDropProb,
		"delay_prob":     payload.DelayProb,
	}

	body, err := json.Marshal(data)
	if err != nil {
		log.Println("❌ Failed to marshal extractor payload:", err)
		http.Error(w, "Failed to prepare extractor request", http.StatusInternalServerError)
		return
	}

	resp, err := http.Post(extractorURL, "application/json", bytes.NewBuffer(body))
	if err != nil {
		log.Printf("❌ Failed to trigger extractor: %v", err)
		http.Error(w, "Failed to start extractor", http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()

	log.Printf("📤 Extractor triggered: %s", resp.Status)
	w.WriteHeader(http.StatusOK)
	w.Write([]byte("✅ Pipeline started"))
}

var completed = make(map[string]map[string]bool)

func handleTrigger(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Only POST allowed", http.StatusMethodNotAllowed)
		return
	}

	var raw map[string]interface{}
	if err := json.NewDecoder(r.Body).Decode(&raw); err != nil {
		log.Println("❌ Failed to decode JSON:", err)
		http.Error(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	// Safely extract values as strings
	get := func(key string) string {
		if val, ok := raw[key]; ok {
			return fmt.Sprintf("%v", val)
		}
		return ""
	}

	event := get("event")
	origin := get("origin")
	date := get("date")
	duration := get("duration")

	log.Printf("📥 Event received: %s from %s | date: %s", event, origin, date)

	// Track and skip duplicates
	if _, ok := completed[date]; !ok {
		completed[date] = make(map[string]bool)
	}
	if completed[date][event] {
		log.Printf("⚠️ Duplicate event %s for date %s — ignoring", event, date)
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("Duplicate event ignored"))
		return
	}
	completed[date][event] = true

	// Duration logging
	if duration != "" {
		filename := "logs/duration_" + origin + ".log"
		if f, err := os.OpenFile(filename, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644); err != nil {
			log.Println("❌ Failed to open duration log:", err)
		} else {
			logLine := fmt.Sprintf("%s,%s,%s\n", date, event, duration)
			if _, err := f.WriteString(logLine); err != nil {
				log.Println("❌ Failed to write duration:", err)
			} else {
				log.Printf("🕒 Logged duration %ss to %s", duration, filename)
			}
			f.Close()
		}
	}

	// === Modified Routing Logic ===
	// This version skips the loader-JSON step to avoid writing to CleanedInspectionRow.
	// Only the loader-parquet step is triggered after the cleaner completes.
	// This ensures the ML pipeline (which depends on CleanedInspectionRow) remains unaffected
	// while allowing the demo pipeline to populate CleanedInspectionColumn for monitoring.

	// Routing logic
	switch event {
	case "extractor_completed":
		log.Println("📤 Forwarding to cleaner...")
		forwardToService(cleanerURL, "Cleaner", map[string]string{"date": date})

	case "cleaner_completed":
		log.Println("📤 Forwarding to loader-parquet (skipping loader-json)...")
		forwardToService(loaderParquetURL, "Loader-Parquet", map[string]string{"date": date})

	case "loader_parquet_completed":
		log.Println("✅ Pipeline completed successfully for date:", date)
	}

	// Routing logic
	// switch event {
	// case "extractor_completed":
	// 	log.Println("📤 Forwarding to cleaner...")
	// 	forwardToService(cleanerURL, "Cleaner", map[string]string{"date": date})

	// case "cleaner_completed":
	// 	log.Println("📤 Forwarding to loader-json...")
	// 	forwardToService(loaderURL, "Loader-JSON", map[string]string{"date": date})

	// case "loader_json_completed":
	// 	log.Println("📤 Forwarding to loader-parquet...")
	// 	forwardToService(loaderParquetURL, "Loader-Parquet", map[string]string{"date": date})

	// case "loader_parquet_completed":
	// 	log.Println("✅ Pipeline completed successfully for date:", date)
	// }

	w.WriteHeader(http.StatusOK)
	w.Write([]byte("✅ Trigger handled successfully"))
}

func main() {
	// Ensure log directory exists
	_ = os.MkdirAll("logs", 0755)

	_ = configure.LoadServiceConfig

	configB64 := os.Getenv("SERVICE_CONFIG_B64")
	if configB64 == "" {
		log.Fatal("❌ SERVICE_CONFIG_B64 is not set")
	}

	decoded, err := base64.StdEncoding.DecodeString(configB64)
	if err != nil {
		log.Fatalf("❌ Failed to decode SERVICE_CONFIG_B64: %v", err)
	}

	var cfg configure.ServiceURLs
	if err := json.Unmarshal(decoded, &cfg); err != nil {
		log.Fatalf("❌ Failed to parse service config: %v", err)
	}

	extractorURL = cfg.Extractor.URL
	cleanerURL = cfg.Cleaner.URL
	loaderURL = cfg.Loader.URL
	loaderParquetURL = cfg.LoaderParquet.URL

	log.Printf("🚀 Trigger service running on :8080")
	log.Printf("🔗 Extractor:       %s", extractorURL)
	log.Printf("🔗 Cleaner:         %s", cleanerURL)
	log.Printf("🔗 Loader-JSON:     %s", loaderURL)
	log.Printf("🔗 Loader-Parquet:  %s", loaderParquetURL)

	http.HandleFunc("/run", handleRun)
	http.HandleFunc("/clean", handleTrigger)
	http.HandleFunc("/purge", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "Only POST allowed", http.StatusMethodNotAllowed)
			return
		}
		completed = make(map[string]map[string]bool)
		log.Println("🧹 Cleared completed event cache")
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("✅ Cache cleared"))
	})

	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		fmt.Fprintf(w, `{"status":"ok", "time":"%s"}`, time.Now().Format(time.RFC3339))
	})

	log.Fatal(http.ListenAndServe(":8080", nil))
}

// func main() {
// 	// Ensure log directory exists
// 	_ = os.MkdirAll("logs", 0755)
// 	configPath := os.Getenv("SERVICE_CONFIG_PATH")
// 	if configPath == "" {
// 		configPath = "/services.json"
// 	}

// 	cfg, err := configure.LoadServiceConfig(configPath)
// 	if err != nil {
// 		log.Fatalf("❌ Failed to load service config: %v", err)
// 	}

// 	extractorURL = cfg.Extractor.URL
// 	cleanerURL = cfg.Cleaner.URL
// 	loaderURL = cfg.Loader.URL
// 	loaderParquetURL = cfg.LoaderParquet.URL

// 	log.Printf("🚀 Trigger service running on :8080")
// 	log.Printf("🔗 Extractor:       %s", extractorURL)
// 	log.Printf("🔗 Cleaner:         %s", cleanerURL)
// 	log.Printf("🔗 Loader-JSON:     %s", loaderURL)
// 	log.Printf("🔗 Loader-Parquet:  %s", loaderParquetURL)

// 	http.HandleFunc("/run", handleRun)
// 	http.HandleFunc("/clean", handleTrigger)

// 	log.Fatal(http.ListenAndServe(":8080", nil))
// }
