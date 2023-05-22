package main

import (
	"fmt"
	"os"
)

func main() {
	checkResult := false
	switch mode := os.Getenv("CHECK_MODE"); mode {
	case "basic":
		checkResult = checkBasic()
	case "tcp_body_filter":
		checkResult = checkBodyFilter()
	case "forwarding_nat":
		checkResult = checkForwardingNAT()
	case "icmp_config":
		checkResult = checkICMPConfig()
	case "http_access":
		checkResult = checkHttpAccess()
	default:
		fmt.Printf("Unknown checking mode %s\n", mode)
		return
	}
	if checkResult {
		fmt.Println("Checks OK")
		if os.Getenv("CHAPTER") != "" {
			client := NewLabClient()
			_ = client.Submit()
		}

		err := os.WriteFile("/out/result", []byte("OK"), 0666)
		if err != nil {
			fmt.Printf("Filed to write checking report: %v\n", err)
		}
	} else {
		fmt.Println("Checks failed")
	}
}
