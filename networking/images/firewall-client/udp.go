package main

import (
	"fmt"
	"net"
	"os"
	"time"
)

func startUDPServer(serverAddr string) error {
	log := func(text string, args ...any) {
		fmt.Printf("[UDP %s] %s %s\n", serverAddr, time.Now().Format(time.RFC3339),
			fmt.Sprintf(text, args...))
	}

	udpServer, err := net.ListenPacket("udp", serverAddr)
	if err != nil {
		return err
	}

	hideRequestSource := os.Getenv("HIDE_REQUEST_SOURCE") != ""

	go func() {
		defer udpServer.Close()

		buf := make([]byte, 1024)
		for {
			_, addr, err := udpServer.ReadFrom(buf)
			if err != nil {
				fmt.Println(err)
				continue
			}
			if hideRequestSource {
				log("received message")
			} else {
				log("received message form %v", addr)
			}
			_, err = udpServer.WriteTo([]byte("Hello, UDP "+addr.String()), addr)
			if err != nil {
				log("failed to send message for %v: %v", addr, err)
			}
		}
	}()
	return nil
}
