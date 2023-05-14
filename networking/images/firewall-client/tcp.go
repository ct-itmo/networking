package main

import (
	"fmt"
	"net"
	"time"
)

func startTCPServer(serverAddr string) error {
	log := func(text string, args ...any) {
		fmt.Printf("[TCP %s] %s %s\n", serverAddr, time.Now().Format(time.RFC3339),
			fmt.Sprintf(text, args...))
	}

	handleIncomingTCPRequest := func(conn net.Conn) {
		buffer := make([]byte, 1024)
		_, err := conn.Read(buffer)
		if err != nil {
			return
		}
		_, err = conn.Write([]byte("Hello, TCP " + conn.RemoteAddr().String()))
		if err != nil {
			log("failed to send message for %v: %v", conn.RemoteAddr(), err)
		}

		conn.Close()
	}

	listen, err := net.Listen("tcp", serverAddr)
	if err != nil {
		return err
	}

	go func() {
		defer listen.Close()

		for {
			conn, err := listen.Accept()
			if err != nil {
				continue
			}
			go handleIncomingTCPRequest(conn)

			log("received message form %v", conn.RemoteAddr())
		}
	}()
	return nil
}
