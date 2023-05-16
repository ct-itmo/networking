package main

import (
	"errors"
	"fmt"
	"net"
	"strings"
	"syscall"
	"time"
)

const udpReadTimeout = time.Millisecond * 500

func checkUdp(addr string) (bool, error) {
	received, err := sendUdp(addr)
	if err != nil {
		return false, err
	}
	return strings.HasPrefix(received, "Hello, UDP"), nil
}

func sendUdp(addr string) (string, error) {
	udpServer, err := net.ResolveUDPAddr("udp", addr)
	if err != nil {
		fmt.Printf("ERROR: resolveUDPAddr %s failed: %v", addr, err.Error())
		return "", err
	}

	conn, err := net.DialUDP("udp", nil, udpServer)
	if err != nil {
		fmt.Printf("ERROR: failed to create udp connection: %v\n", err.Error())
		return "", err
	}

	defer conn.Close()
	_, err = conn.Write([]byte("Hello UDP server"))
	if err != nil {
		fmt.Printf("ERROR: failed send data using udp: %v\n", err.Error())
		return "", err
	}

	received := make([]byte, 1024)
	conn.SetReadDeadline(time.Now().Add(udpReadTimeout))
	receivedLen, err := conn.Read(received)
	if err != nil {
		if nerr, ok := err.(net.Error); ok && nerr.Timeout() || errors.Is(err, syscall.ECONNREFUSED) {
			return "", nil
		}
		fmt.Printf("ERROR: failed to receive data using udp: %v\n", err.Error())
		return "", err
	}
	received = received[:receivedLen]
	return string(received), nil
}
