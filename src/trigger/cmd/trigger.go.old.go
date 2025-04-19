package main

import (
	"bytes"
	"configure"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"os"
	"strconv"
	"time"
)

type StageEvent struct {
	Timestamp time.Time
	Event     string
}

type PipelineState struct {
	StartTime  time.Time
	Date       string
	MaxOffset  int
	StageTimes map[string]time.Time
	Stages     []StageEvent
}

var cleanerURL string
var loaderURL string
var loaderParquetURL string
var pipeline PipelineState
var extractorURL string

func handleRun(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Only POST allowed", http.StatusMethodNotAllowed)
		return
	}

	var payload struct {
		Date      string `json:"date"`
		MaxOffset int    `json:"max_offset"`
	}

	if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
		http.Error(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	pipeline = PipelineState{
		StartTime:  time.Now(),
		Date:       payload.Date,
		MaxOffset:  payload.MaxOffset,
		StageTimes: map[string]time.Time{"extractor_started": time.Now()},
	}

	log.Printf("🚀 Pipeline run started for date=%s with max_offset=%d", payload.Date, payload.MaxOffset)

	// POST to extractor
	data := map[string]any{
		"date":       payload.Date,
		"max_offset": payload.MaxOffset,
	}
	body, _ := json.Marshal(data)

	resp, err := http.Post(extractorURL, "application/json", bytes.NewBuffer(body))
	if err != nil {
		log.Printf("❌ Failed to start extractor: %v", err)
		http.Error(w, "Extractor failed", http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()

	log.Printf("📤 Extractor triggered with status: %s", resp.Status)
	w.WriteHeader(http.StatusOK)
	w.Write([]byte("Pipeline started"))
}

func parseInt(val string) int {
	i, _ := strconv.Atoi(val)
	return i
}

func handleTrigger(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Only POST allowed", http.StatusMethodNotAllowed)
		return
	}

	var payload map[string]string
	if err := json.NewDecoder(r.Body).Decode(&payload); err != nil {
		http.Error(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	origin := payload["origin"]
	event := payload["event"]
	timestamp := time.Now()

	log.Printf("📦 Received request: origin=%s | payload=%v\n", origin, payload)

	// If pipeline already completed, ignore any further processing
	if len(pipeline.Stages) > 0 {
		last := pipeline.Stages[len(pipeline.Stages)-1]
		if last.Event == "loader_parquet_completed" {
			log.Printf("⛔ Pipeline already completed. Ignoring request from: %s", origin)
			w.WriteHeader(http.StatusOK)
			w.Write([]byte("⛔ Pipeline already completed"))
			return
		}
	}

	// Stage tracking
	if event != "" {
		log.Printf("📥 Event received: %s from %s", event, origin)
		pipeline.Stages = append(pipeline.Stages, StageEvent{
			Event:     event,
			Timestamp: timestamp,
		})
	}

	// Pipeline lifecycle handling
	switch event {
	case "extractor_started":
		pipeline.Date = payload["date"]
		pipeline.MaxOffset = parseInt(payload["max_offset"])
		pipeline.StartTime = timestamp

	case "extractor_completed":
		log.Printf("⏱️ Extractor finished. Triggering cleaner for date: %s", pipeline.Date)
		forwardTo(cleanerURL, map[string]string{"date": pipeline.Date}, "Cleaner")

	case "cleaner_completed":
		log.Printf("✅ Cleaner finished. Triggering loader-json for date: %s", pipeline.Date)
		forwardTo(loaderURL, map[string]string{"date": pipeline.Date}, "Loader-json")

	case "loader_json_completed":
		log.Printf("✅ Loader-json finished. Triggering loader-parquet for date: %s", pipeline.Date)
		forwardTo(loaderParquetURL, map[string]string{"date": pipeline.Date}, "Loader-parquet")

	case "loader_parquet_completed":
		log.Printf("✅ Loader-parquet completed for date: %s", pipeline.Date)
		reportPipelineTiming()
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("✅ Pipeline completed"))
		return
	}

	// If it's just a routed message without event, still allow routing
	if event == "" {
		var forwardURL string

		switch origin {
		case "cleaner":
			forwardURL = loaderURL
			log.Println("🔁 Routing cleaner output to loader-json")
		case "json_loader":
			forwardURL = loaderParquetURL
			log.Println("🔁 Routing loader-json output to loader-parquet")
		default:
			forwardURL = cleanerURL
			log.Println("🔁 Routing extractor output to cleaner")
		}

		if forwardURL == "" {
			http.Error(w, "No forwarding URL configured", http.StatusInternalServerError)
			return
		}

		data, _ := json.Marshal(payload)
		resp, err := http.Post(forwardURL, "application/json", bytes.NewBuffer(data))
		if err != nil {
			log.Printf("❌ Failed to forward to %s: %v", forwardURL, err)
			http.Error(w, "Forwarding failed", http.StatusBadGateway)
			return
		}
		defer resp.Body.Close()

		body, _ := io.ReadAll(resp.Body)
		log.Printf("✅ Trigger forwarded from origin=%s to %s | Status: %s | Response: %s",
			origin, forwardURL, resp.Status, string(body))

		w.WriteHeader(resp.StatusCode)
		w.Write([]byte("Forwarded successfully"))
		return
	}

	w.WriteHeader(http.StatusOK)
	w.Write([]byte("✅ Event handled"))
}

func forwardTo(url string, payload map[string]string, label string) {
	body, _ := json.Marshal(payload)
	resp, err := http.Post(url, "application/json", bytes.NewBuffer(body))
	if err != nil {
		log.Printf("❌ Failed to start %s: %v", label, err)
	} else {
		log.Printf("✅ %s triggered: %s", label, resp.Status)
		resp.Body.Close()
	}
}

func reportPipelineTiming() {
	start := pipeline.StartTime
	t := func(stage string) time.Time {
		for _, s := range pipeline.Stages {
			if s.Event == stage {
				return s.Timestamp
			}
		}
		return time.Time{}
	}

	extractEnd := t("extractor_completed")
	cleanEnd := t("cleaner_completed")
	jsonEnd := t("loader_json_completed")
	parquetEnd := t("loader_parquet_completed")

	log.Println("📊 Pipeline completed — duration breakdown:")
	if !extractEnd.IsZero() {
		log.Printf("🕒 extractor:       %.2fs", extractEnd.Sub(start).Seconds())
	}
	if !cleanEnd.IsZero() {
		log.Printf("🕒 cleaner:         %.2fs", cleanEnd.Sub(extractEnd).Seconds())
	}
	if !jsonEnd.IsZero() {
		log.Printf("🕒 loader-json:     %.2fs", jsonEnd.Sub(cleanEnd).Seconds())
	}
	if !parquetEnd.IsZero() {
		log.Printf("🕒 loader-parquet:  %.2fs", parquetEnd.Sub(jsonEnd).Seconds())
		log.Printf("🟢 total time:      %.2fs", parquetEnd.Sub(start).Seconds())
	}
}

func main() {
	// Load service URL configuration
	configPath := os.Getenv("SERVICE_CONFIG_PATH")
	if configPath == "" {
		configPath = "/services.json"
	}
	cfg, err := configure.LoadServiceConfig(configPath)
	if err != nil {
		log.Fatalf("❌ Failed to load service config: %v", err)
	}
	http.HandleFunc("/run", handleRun)

	extractorURL = cfg.Extractor.URL
	cleanerURL = cfg.Cleaner.URL
	loaderURL = cfg.Loader.URL
	loaderParquetURL = cfg.LoaderParquet.URL

	log.Printf("🚀 Trigger service running on :8080 — forwarding to cleaner at %s\n", cleanerURL)
	http.HandleFunc("/clean", handleTrigger)
	log.Fatal(http.ListenAndServe(":8080", nil))
}
