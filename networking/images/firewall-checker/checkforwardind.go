package main

import (
	"fmt"
	"os"
	"strings"
)

func logConnectionResult(requestType string, addr string, requestResult bool, requestErr error, expectedResult bool, portType string) {
	if requestErr != nil {
		fmt.Println("Unexpected error in checker. Ask administrator")
		return
	}
	if portType != "" {
		portType = " (" + portType + " port)"
	}
	fmt.Printf("%s from %s to %s%s: %s (expected %s)\n",
		requestType, os.Getenv("BOX_NETWORK_NAME"), addr,
		portType, formatCheckResult(requestResult), formatCheckResult(expectedResult))
}

func checkForwarding() bool {
	checkResult := true

	validUDPAddreses := os.Getenv("UDP_VALID_ADDRESSES")
	for _, addr := range strings.Split(validUDPAddreses, ",") {
		if addr == "" {
			continue
		}
		ok, err := checkUdp(addr)
		logConnectionResult("UDP", addr, ok, err, true, "")
		checkResult = err == nil && ok && checkResult
	}

	validTCPAddreses := os.Getenv("TCP_VALID_ADDRESSES")
	for _, addr := range strings.Split(validTCPAddreses, ",") {
		if addr == "" {
			continue
		}
		ok, err := checkTcp(addr)
		logConnectionResult("TCP", addr, ok, err, true, "")
		checkResult = checkResult && err == nil && ok
	}

	return checkResult
}

func checkTCPUnidirectional() bool {
	checkResult := true
	validUDPAddreses := os.Getenv("UDP_VALID_ADDRESSES")
	for _, addr := range strings.Split(validUDPAddreses, ",") {
		if addr == "" {
			continue
		}
		ok, err := checkUdp(addr)
		logConnectionResult("UDP", addr, ok, err, true, "")
		checkResult = checkResult && err == nil && ok
	}

	invalidUDPAddreses := os.Getenv("UDP_INVALID_ADDRESSES")
	for _, addr := range strings.Split(invalidUDPAddreses, ",") {
		if addr == "" {
			continue
		}
		ok, err := checkUdp(addr)
		logConnectionResult("UDP", addr, ok, err, false, "no acessable")
		checkResult = checkResult && err == nil && !ok
	}

	validTCPAddreses := os.Getenv("TCP_VALID_ADDRESSES")
	for _, addr := range strings.Split(validTCPAddreses, ",") {
		if addr == "" {
			continue
		}
		ok, err := checkTcp(addr)
		logConnectionResult("TCP", addr, ok, err, true, "")
		checkResult = checkResult && err == nil && ok
	}

	invalidTCPAddreses := os.Getenv("TCP_INVALID_ADDRESSES")
	for _, addr := range strings.Split(invalidTCPAddreses, ",") {
		if addr == "" {
			continue
		}
		ok, err := checkTcp(addr)
		logConnectionResult("TCP", addr, ok, err, false, "")
		checkResult = checkResult && err == nil && !ok
	}

	return checkResult
}

func checkBodyFilter() bool {
	checkResult := true
	badWord := os.Getenv("BAD_WORD")
	addr := strings.Split(os.Getenv("TCP_VALID_ADDRESSES"), ",")[0]
	if addr == "" {
		fmt.Println("No TCP addr for filter check")
		return false
	}

	checkContent := func(content string, mustOk bool) {
		fmt.Printf("Send '%s'\n", content)
		ok, err := checkTcpWithContent(addr, content)
		logConnectionResult("TCP", addr, ok, err, mustOk, "")
		checkResult = err == nil && ok == mustOk && checkResult
	}

	checkContent("Hello!", true)
	checkContent(badWord, false)
	checkContent("Hello! "+badWord+" Goodbye!", false)
	checkContent("What is the good today?", true)
	checkContent(badWord[1:len(badWord)], true)
	checkContent(badWord[0:len(badWord)-1], true)
	x := len(badWord) / 2
	checkContent(badWord[0:x]+"hahaha"+badWord[x:len(badWord)], true)
	checkContent(badWord+" or not "+badWord, false)

	return checkResult
}

func checkForwardingNAT() bool {
	checkResult := true

	validUDPAddreses := os.Getenv("UDP_VALID_ADDRESSES")
	for _, addr := range strings.Split(validUDPAddreses, ",") {
		if addr == "" {
			continue
		}
		message, err := sendUdp(addr)
		fmt.Println(message)
		ok := strings.HasPrefix(message, "Hello, UDP "+os.Getenv("NAT_IP"))
		logConnectionResult("UDP", addr, ok, err, true, "")
		checkResult = err == nil && ok && checkResult
	}

	validTCPAddreses := os.Getenv("TCP_VALID_ADDRESSES")
	for _, addr := range strings.Split(validTCPAddreses, ",") {
		if addr == "" {
			continue
		}
		message, err := sendTcp(addr, "Hello TCP server")
		fmt.Println(message)
		ok := strings.HasPrefix(message, "Hello, TCP "+os.Getenv("NAT_IP"))
		logConnectionResult("TCP", addr, ok, err, true, "")
		checkResult = checkResult && err == nil && ok
	}

	return checkResult
}
