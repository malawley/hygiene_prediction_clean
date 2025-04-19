package configure

import (
	"encoding/json"
	"fmt"
	"os"
)

type ServiceURLs struct {
	Extractor struct {
		URL string `json:"url"`
	} `json:"extractor"`
	Cleaner struct {
		URL string `json:"url"`
	} `json:"cleaner"`
	Trigger struct {
		URL string `json:"url"`
	} `json:"trigger"`
	Loader struct {
		URL string `json:"url"`
	} `json:"loader"`
	LoaderParquet struct {
		URL string `json:"url"`
	} `json:"loader_parquet"`
}

func LoadServiceConfig(path string) (*ServiceURLs, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("failed to read service config: %w", err)
	}
	var cfg ServiceURLs
	if err := json.Unmarshal(data, &cfg); err != nil {
		return nil, fmt.Errorf("failed to parse service config: %w", err)
	}
	return &cfg, nil
}
