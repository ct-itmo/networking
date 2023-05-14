package main

func formatCheckResult(isOk bool) string {
	if isOk {
		return "OK"
	}
	return "NO"
}
