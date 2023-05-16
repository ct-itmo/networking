package main

import (
	"crypto/sha256"
	"fmt"
	"io/ioutil"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/go-ping/ping"
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

// TODO: refactor
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

func checkICMPConfig() bool {
	host := strings.Split(os.Getenv("PING_VALID_IPS"), ",")[0]
	expectedTTL, err := strconv.Atoi(os.Getenv("PING_EXPECTED_TTL"))
	if err != nil {
		fmt.Println("Invalid PING_EXPECTED_TTL variable")
		return false
	}

	pinger, err := ping.NewPinger(host)
	if err != nil {
		fmt.Printf("Invalid host %s: %v\n", host, err)
		return false
	}
	pinger.Count = 12
	pinger.Size = 128
	pinger.TTL = 64
	pinger.Timeout = 15 * time.Second
	// pinger.SetPrivileged(true)

	ttlOk := true
	pinger.OnRecv = func(p *ping.Packet) {
		if ttlOk && p.Ttl != expectedTTL {
			fmt.Printf("Received ICMP with TTL %d, but excepted %d\n", p.Ttl, expectedTTL)
			ttlOk = false
		}
	}

	if err = pinger.Run(); err != nil {
		fmt.Printf("Failed to ping host %v: %v\n", host, err)
		return false
	}
	stats := pinger.Statistics()
	fmt.Printf("%d packets transmitted, %d received, %f%% packet loss to %s\n", stats.PacketsSent, stats.PacketsRecv,
		stats.PacketLoss, host)

	return stats.PacketsSent == pinger.Count && 15 <= stats.PacketLoss && stats.PacketLoss <= 35 && stats.PacketsRecvDuplicates == 0 && ttlOk
}

func logHttpResult(url string, requestResult bool, expectedResult bool) {
	fmt.Printf("HTTP acces to %s %s (expected %s)\n",
		url, formatCheckResult(requestResult), formatCheckResult(expectedResult))
}

func checkHttpAccess() bool {
	checkResult := true
	httpClient := http.Client{Timeout: 1 * time.Second}

	validUrls := strings.Split(os.Getenv("HTTP_VALID_URLS"), ",")
	for _, url := range validUrls {
		if url == "" {
			continue
		}
		_, err := httpClient.Get(url)
		logHttpResult(url, err == nil, true)
		checkResult = checkResult && err == nil
	}

	for _, url := range strings.Split(os.Getenv("HTTP_INVALID_URLS"), ",") {
		if url == "" {
			continue
		}
		_, err := httpClient.Get(url)
		logHttpResult(url, err == nil, false)
		checkResult = checkResult && err != nil
	}

	secretSeed := os.Getenv("SECRET_SEED")
	message := fmt.Sprintf("%s_%s_%s", os.Getenv("TASK"), os.Getenv("USER_ID"), time.Now().Format(time.RFC3339Nano))
	messageKey := fmt.Sprintf("%x", sha256.Sum256([]byte(message+"_"+secretSeed)))
	expectedSignature := fmt.Sprintf("%x",
		sha256.Sum256([]byte(fmt.Sprintf("OK_%s_%s_%s", message, messageKey, secretSeed))))

	responce, err := httpClient.Get(validUrls[0] + "/api/signature?message=" + message + "&key=" + messageKey)
	if err != nil {
		logHttpResult(validUrls[0], false, true)
		return false
	}
	signature, err := ioutil.ReadAll(responce.Body)
	if err != nil {
		fmt.Println("HTTP failed to read http responce")
		return false
	}
	if expectedSignature != string(signature) {
		fmt.Println("Invalid HTTP checker server signature")
		return false
	}

	return checkResult
}
