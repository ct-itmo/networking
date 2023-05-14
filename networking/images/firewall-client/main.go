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

	startUDPServer(os.Getenv("BOX_IP") + ":3001")
	startTCPServer(os.Getenv("BOX_IP") + ":3002")

	for _, addr := range strings.Split(os.Getenv("OTHER_UDP_SERVER"), ",") {
		if addr == "" {
			continue
		}
		startUDPServer(addr)
	}

	if os.Getenv("TIMEOUT") != "" {
		timeout, err := time.ParseDuration(os.Getenv("TIMEOUT"))
		if err != nil {
			fmt.Println("Invalid server timeout")
			return
		}

		select {
		case _ = <-time.After(timeout):
		case _ = <-done:
		}

	} else {
		<-done
	}
	fmt.Println("Server stopped")
}
