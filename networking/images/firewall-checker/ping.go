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
	// fmt.Printf("Ping %s: %d packets transmitted, %d packets received, %d duplicates, %v%% packet loss\n",
	// stats.Addr, stats.PacketsSent, stats.PacketsRecv, stats.PacketsRecvDuplicates, stats.PacketLoss)

	return stats.PacketsSent == countOfPackages && stats.PacketsRecv == countOfPackages &&
		stats.PacketsRecvDuplicates == 0, nil
}
