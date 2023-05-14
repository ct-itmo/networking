package main

import (
	"fmt"
	"os"
)

func main() {
	checkResult := false
	switch mode := os.Getenv("CHECK_MODE"); mode {
	case "setup":
		checkResult = checkPings()
	case "forwarding":
		checkResult = checkPings()
		checkResult = checkForwarding() && checkResult
	case "tcp_unidirectional":
		checkResult = checkPings()
		checkResult = checkTCPUnidirectional() && checkResult
	case "tcp_body_filter":
		checkResult = checkBodyFilter()
	case "forwarding_nat":
		checkResult = checkForwardingNAT()
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
