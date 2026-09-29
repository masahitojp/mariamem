package main

import (
	"errors"
	"os"
	"strconv"
	"testing"
)

func TestResourceCountersAndCPUIntervals(t *testing.T) {
	private := int64(70)
	row, err := sumResources(map[string]resource{"host": {Primary: 100, RSS: 150, CPU: 1, Private: &private}, "guest": {Primary: 200, RSS: 250, CPU: 2, Private: &private}})
	if err != nil || row.Primary != 300 || *row.Private != 140 || row.RSS != 400 {
		t.Fatal(row, err)
	}
	if _, err := sumResources(map[string]resource{"guest": {Error: "unavailable"}}); !errors.Is(err, errCountersUnavailable) {
		t.Fatal(err)
	}
	host := strconv.Itoa(os.Getpid())
	h, r := groupCPU(groupCost{Members: map[string]resource{host: {CPU: 1}}}, groupCost{Members: map[string]resource{host: {CPU: 1.5}, "guest": {CPU: .3}}})
	if h != .5 || r != .3 {
		t.Fatal(h, r)
	}
}
