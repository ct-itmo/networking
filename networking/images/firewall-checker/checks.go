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

func logPingResult(ip string, pingResult bool, pingErr error, expecredResult bool) {
	if pingErr != nil {
		fmt.Printf("Unexpected error in checker. Ask administrator")
		return
	}
	fmt.Printf("Ping from %s to %s: %s (expected %s)\n",
		os.Getenv("BOX_NETWORK_NAME"), ip, formatCheckResult(pingResult), formatCheckResult(expecredResult))
}

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

func checkBasic() bool {
	checkResult := checkByEnvList("PING_VALID_IPS", func(ip string) bool {
		ok, err := checkPing(ip)
		logPingResult(ip, ok, err, true)
		return err == nil && ok
	})

	checkResult = checkByEnvList("PING_INVALID_IPS", func(ip string) bool {
		ok, err := checkPing(ip)
		logPingResult(ip, ok, err, false)
		return err == nil && !ok
	}) && checkResult

	checkResult = checkByEnvList("UDP_VALID_ADDRESSES", func(addr string) bool {
		ok, err := checkUdp(addr)
		logConnectionResult("UDP", addr, ok, err, true, "")
		return err == nil && ok
	}) && checkResult

	checkResult = checkByEnvList("UDP_INVALID_ADDRESSES", func(addr string) bool {
		ok, err := checkUdp(addr)
		logConnectionResult("UDP", addr, ok, err, false, "no acessable")
		return err == nil && !ok
	}) && checkResult

	checkResult = checkByEnvList("TCP_VALID_ADDRESSES", func(addr string) bool {
		ok, err := checkTcp(addr)
		logConnectionResult("TCP", addr, ok, err, true, "")
		return err == nil && ok
	}) && checkResult

	checkResult = checkByEnvList("TCP_INVALID_ADDRESSES", func(addr string) bool {
		ok, err := checkTcp(addr)
		logConnectionResult("TCP", addr, ok, err, false, "")
		return err == nil && !ok
	}) && checkResult

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
	checkContent(badWord[1:], true)
	checkContent(badWord[0:len(badWord)-1], true)
	x := len(badWord) / 2
	checkContent(badWord[0:x]+"hahaha"+badWord[x:], true)
	checkContent(badWord+" or not "+badWord, false)

	return checkResult
}

func checkForwardingNAT() bool {
	checkResult := checkByEnvList("UDP_VALID_ADDRESSES", func(addr string) bool {
		message, err := sendUdp(addr)
		ok := strings.HasPrefix(message, "Hello, UDP "+os.Getenv("NAT_IP"))
		logConnectionResult("UDP", addr, ok, err, true, "")
		if err == nil && !ok {
			fmt.Println("[server received request, but request source address isn't firewall address]")
		}
		return err == nil && ok
	})
	checkResult = checkByEnvList("TCP_VALID_ADDRESSES", func(addr string) bool {
		message, err := sendTcp(addr, "Hello TCP server")
		ok := strings.HasPrefix(message, "Hello, TCP "+os.Getenv("NAT_IP"))
		logConnectionResult("TCP", addr, ok, err, true, "")
		if err == nil && !ok {
			fmt.Println("[server received request, but request source address isn't firewall address]")
		}
		return err == nil && ok
	}) && checkResult

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

	checkResult = checkByEnvList("HTTP_VALID_URLS", func(url string) bool {
		_, err := httpClient.Get(url)
		logHttpResult(url, err == nil, true)
		return err == nil
	}) && checkResult

	checkResult = checkByEnvList("HTTP_INVALID_URLS", func(url string) bool {
		_, err := httpClient.Get(url)
		logHttpResult(url, err == nil, false)
		return err != nil
	}) && checkResult

	secretSeed := os.Getenv("SECRET_SEED")
	message := fmt.Sprintf("%s_%s_%s", os.Getenv("TASK"), os.Getenv("USER_ID"), time.Now().Format(time.RFC3339Nano))
	messageKey := fmt.Sprintf("%x", sha256.Sum256([]byte(message+"_"+secretSeed)))
	expectedSignature := fmt.Sprintf("%x",
		sha256.Sum256([]byte(fmt.Sprintf("OK_%s_%s_%s", message, messageKey, secretSeed))))

	validUrls := strings.Split(os.Getenv("HTTP_VALID_URLS"), ",")
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
