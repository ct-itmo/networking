package main

import (
	"fmt"
	"time"

	"github.com/go-ping/ping"
)

const countOfPackages = 3

func checkPing(host string) (bool, error) {
	pinger, err := ping.NewPinger(host)
	if err != nil {
		fmt.Printf("Invalid host %s: %v\n", host, err)
		return false, err
	}
	pinger.Count = countOfPackages
	pinger.Size = 128
	pinger.TTL = 64
	pinger.Timeout = 5 * time.Second
	// pinger.SetPrivileged(true)

	if err = pinger.Run(); err != nil {
		fmt.Printf("Failed to ping host %v: %v\n", host, err)
		return false, err
	}
	stats := pinger.Statistics()

	return stats.PacketsSent == countOfPackages && stats.PacketsRecv > 0 &&
		stats.PacketsRecvDuplicates == 0, nil
}
