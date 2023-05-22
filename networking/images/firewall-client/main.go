package main

import (
	"fmt"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"
)

const logTimeFormat = "2006-01-02T15:04:05.999"

func main() {
	done := make(chan os.Signal, 1)
	signal.Notify(done, os.Interrupt, syscall.SIGINT, syscall.SIGTERM)

	for _, addr := range strings.Split(os.Getenv("UDP_SERVERS"), ",") {
		if addr == "" {
			continue
		}
		startUDPServer(addr)
	}

	for _, addr := range strings.Split(os.Getenv("TCP_SERVERS"), ",") {
		if addr == "" {
			continue
		}
		startTCPServer(addr)
	}

	for _, addr := range strings.Split(os.Getenv("HTTP_SERVERS"), ",") {
		if addr == "" {
			continue
		}
		startHTTPServer(addr)
	}

	if os.Getenv("TIMEOUT") != "" {
		timeout, err := time.ParseDuration(os.Getenv("TIMEOUT"))
		if err != nil {
			fmt.Println("Invalid server timeout")
			return
		}

		select {
		case <-time.After(timeout):
		case <-done:
		}

	} else {
		<-done
	}
	fmt.Println("Server stopped")
}
