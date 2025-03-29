package main

import (
    "fmt"
    "os/exec"
)

func main() {
    // Optional: path to your BAT file
    scriptPath := "C:\\Users\\malaw\\OneDrive\\Documents\\MSDS\\MSDS434\\hygiene_prediction\\start_minio.bat"

    fmt.Println("Starting MinIO server...")

    cmd := exec.Command("cmd", "/C", scriptPath)
    err := cmd.Start()
    if err != nil {
        fmt.Printf("❌ Failed to start MinIO: %v\n", err)
        return
    }

    fmt.Println("✅ MinIO launched. Proceeding with extraction...")

    // TODO: Add your data extraction logic here
}
