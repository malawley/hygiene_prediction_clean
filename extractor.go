package main

import (
    "fmt"
    "os/exec"
)


package main

import (
	"fmt"
	"io"
	"net/http"
	"os"
)

func main() {
	// Define the URL we want to fetch
	url := "https://data.cityofchicago.org/resource/qizy-d2wf.json?$limit=1000&$offset=0"

	// Make the GET request to the API
	response, err := http.Get(url)
	if err != nil {
		fmt.Println("Error fetching data:", err)
		return
	}
	defer response.Body.Close()

	// Check for HTTP errors
	if response.StatusCode != http.StatusOK {
		fmt.Println("Unexpected status code:", response.StatusCode)
		return
	}

	// Create a local file to save the data
	file, err := os.Create("offset_0.json")
	if err != nil {
		fmt.Println("Error creating file:", err)
		return
	}
	defer file.Close()

	// Copy the response body into the file
	_, err = io.Copy(file, response.Body)
	if err != nil {
		fmt.Println("Error writing to file:", err)
		return
	}

	fmt.Println("✅ Successfully saved offset_0.json")
}



// func main() {
//     // Optional: path to your BAT file
//     scriptPath := "C:\\Users\\malaw\\OneDrive\\Documents\\MSDS\\MSDS434\\hygiene_prediction\\start_minio.bat"

//     fmt.Println("Starting MinIO server...")

//     cmd := exec.Command("cmd", "/C", scriptPath)
//     err := cmd.Start()
//     if err != nil {
//         fmt.Printf("❌ Failed to start MinIO: %v\n", err)
//         return
//     }

//     fmt.Println("✅ MinIO launched. Proceeding with extraction...")

//     // TODO: Add your data extraction logic here
// }



set GOOGLE_APPLICATION_CREDENTIALS=C:\Users\malaw\OneDrive\Documents\MSDS\hygiene-prediction-48fe02c5707d.json