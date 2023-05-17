package main

import (
	"os"
	"strings"
)

func formatCheckResult(isOk bool) string {
	if isOk {
		return "OK"
	}
	return "NO"
}

func checkByEnvList(envName string, checker func(elem string) bool) bool {
	result := true
	for _, elem := range strings.Split(os.Getenv(envName), ",") {
		if elem == "" {
			continue
		}
		result = checker(elem) && result
	}
	return result
}
