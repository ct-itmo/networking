package main

import (
	"fmt"
	"os"
	"strings"
)

func logPingResult(ip string, pingResult bool, pingErr error, expecredResult bool) {
	if pingErr != nil {
		fmt.Printf("Unexpected error in checker. Ask administrator")
		return
	}
	fmt.Printf("Ping from %s to %s: %s (expected %s)\n",
		os.Getenv("BOX_NETWORK_NAME"), ip, formatCheckResult(pingResult), formatCheckResult(expecredResult))
}

func checkPings() bool {
	validIps := os.Getenv("PING_VALID_IPS")
	invalidIps := os.Getenv("PING_INVALID_IPS")
	validPingOk := true
	var err error
	var ok bool
	for _, ip := range strings.Split(validIps, ",") {
		if ip == "" {
			continue
		}
		ok, err = checkPing(ip)
		logPingResult(ip, ok, err, true)
		if err == nil {
			validPingOk = validPingOk && ok
		}
	}

	invalidPingOk := true
	for _, ip := range strings.Split(invalidIps, ",") {
		if ip == "" {
			continue
		}
		ok, err = checkPing(ip)
		logPingResult(ip, ok, err, false)
		if err == nil {
			invalidPingOk = invalidPingOk && !ok
		}
	}

	return validPingOk && invalidPingOk
}
