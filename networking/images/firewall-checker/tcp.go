package main

import (
	"errors"
	"fmt"
	"net"
	"strings"
	"syscall"
	"time"
)

const tcpConnectTimeout = time.Millisecond * 500
const tcpReadTimeout = time.Millisecond * 500

func checkTcp(addr string) (bool, error) {
	return checkTcpWithContent(addr, "Hello tcp server")
}

func checkTcpWithContent(addr string, body string) (bool, error) {
	received, err := sendTcp(addr, body)
	if err != nil {
		return false, err
	}
	return strings.HasPrefix(received, "Hello, TCP"), nil
}

func sendTcp(addr string, body string) (string, error) {
	conn, err := net.DialTimeout("tcp", addr, tcpConnectTimeout)
	if err != nil {
		if nerr, ok := err.(net.Error); ok && nerr.Timeout() || errors.Is(err, syscall.ECONNREFUSED) {
			return "", nil
		}
		fmt.Printf("ERROR: failed to create tcp connection: %v\n", err.Error())
		return "", err
	}

	defer conn.Close()
	_, err = conn.Write([]byte(body))
	if err != nil {
		if nerr, ok := err.(net.Error); ok && nerr.Timeout() || errors.Is(err, syscall.ECONNREFUSED) {
			return "", nil
		}
		fmt.Printf("ERROR: failed send data using udp: %v\n", err.Error())
		return "", err
	}

	received := make([]byte, 1024)
	conn.SetReadDeadline(time.Now().Add(tcpReadTimeout))
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
