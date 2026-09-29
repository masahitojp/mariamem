package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"strconv"
	"sync"
	"time"
)

type resource struct {
	RSS           int64   `json:"rss_bytes"`
	Primary       int64   `json:"primary_bytes"`
	Private       *int64  `json:"private_bytes"`
	CPU           float64 `json:"cpu_seconds"`
	Error         string  `json:"error,omitempty"`
	TimebaseNumer uint32  `json:"cpu_timebase_numer,omitempty"`
	TimebaseDenom uint32  `json:"cpu_timebase_denom,omitempty"`
}
type groupCost struct {
	Members    map[string]resource `json:"members"`
	Primary    int64               `json:"primary_bytes"`
	RSS        int64               `json:"rss_bytes"`
	Private    *int64              `json:"private_bytes"`
	Collection float64             `json:"collection_seconds"`
	At         float64             `json:"at_seconds"`
}

var collectionLock sync.Mutex

func resourceCost() (c groupCost, err error) {
	collectionLock.Lock()
	defer collectionLock.Unlock()
	begin := time.Now()
	ps, e := readCost()
	if e != nil {
		return c, e
	}
	args := []string{strconv.Itoa(os.Getpid())}
	for pid := range ps.Members {
		args = append(args, pid)
	}
	data, e := exec.Command(os.Getenv("MARIAMEM_COST_HELPER"), args...).Output()
	if e != nil {
		return c, e
	}
	if e = json.Unmarshal(data, &c.Members); e != nil {
		return c, e
	}
	if len(c.Members) != len(args) {
		return c, errors.New("process counter inventory mismatch")
	}
	for _, pid := range args {
		if _, ok := c.Members[pid]; !ok {
			return c, errors.New("missing process counters")
		}
	}
	c, e = sumResources(c.Members)
	if e != nil {
		return c, e
	}

	c.Collection = time.Since(begin).Seconds()
	return c, nil
}

// Short-lived/newly spawned processes may disappear or have no accountable
// pages yet. Ready/baseline callers require complete counters; the startup
// peak sampler retains these as gaps and never substitutes zero memory.
var errCountersUnavailable = errors.New("process counters temporarily unavailable")

func sumResources(members map[string]resource) (c groupCost, err error) {
	c.Members = members
	for pid, m := range members {
		if m.Primary < 0 || m.RSS < 0 || m.CPU < 0 {
			return c, fmt.Errorf("invalid process counters for pid %s: %+v", pid, m)
		}
		if m.Error != "" || m.Primary == 0 || m.RSS == 0 {
			return c, fmt.Errorf("%w: pid %s: %+v", errCountersUnavailable, pid, m)
		}
		c.Primary += m.Primary
		c.RSS += m.RSS
		if m.Private != nil {
			if c.Private == nil {
				v := int64(0)
				c.Private = &v
			}
			*c.Private += *m.Private
		}
	}
	return c, nil
}
