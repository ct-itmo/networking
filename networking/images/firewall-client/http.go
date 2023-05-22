package main

import (
	"fmt"
	"io"
	"net/http"
	"time"
)

func startHTTPServer(serverAddr string) error {
	log := func(text string, args ...any) {
		fmt.Printf("[HTTP %s] %s %s\n", serverAddr, time.Now().Format(time.RFC3339),
			fmt.Sprintf(text, args...))
	}

	getRoot := func(w http.ResponseWriter, r *http.Request) {
		log("received get request form %v", r.RemoteAddr)
		io.WriteString(w, "Hello, HTTP")
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/", getRoot)

	go func() {
		err := http.ListenAndServe(serverAddr, mux)
		if err != nil {
			log("HTTP server error %v", err)
		}
	}()
	return nil
}
