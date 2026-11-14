//go:build integration

package mariamemtest

import (
	"os"
	"testing"
)

func TestCampaignRetainedImageCleanup(t *testing.T) {
	stats := map[string]any{"builds": 1, "owned_fds": 1, "process_lifetime": true, "failed": false, "closed": false, "cleanup_debt": false, "image_allocated_bytes": int64(4096)}
	sample := campaignSample{Unlinked: 4096, UnlinkedFiles: 1}
	if !retainedImageOnly(sample, stats) {
		t.Fatal("healthy image rejected")
	}
	for _, key := range []string{"builds", "owned_fds", "process_lifetime", "failed", "closed", "cleanup_debt", "image_allocated_bytes"} {
		old := stats[key]
		delete(stats, key)
		if retainedImageOnly(sample, stats) {
			t.Fatalf("missing %s accepted", key)
		}
		stats[key] = old
	}
	for _, bad := range []campaignSample{{Unlinked: 4096, UnlinkedFiles: 2}, {Unlinked: 4608, UnlinkedFiles: 1}, {UnlinkedFiles: 1}} {
		if retainedImageOnly(bad, stats) {
			t.Fatal("extra/unknown file accepted")
		}
	}
	cold := map[string]any{"builds": 0, "owned_fds": 0, "failed": false, "cleanup_debt": false}
	if !retainedImageOnly(campaignSample{}, cold) {
		t.Fatal("pre-admission guard cleanup rejected")
	}
	if retainedImageOnly(campaignSample{UnlinkedFiles: 1}, cold) {
		t.Fatal("empty-file leak accepted before initialization")
	}
}

func TestCampaignCountsEmptyUnlinkedFiles(t *testing.T) {
	_, bytes, _, files, err := fdInventory()
	if err != nil {
		t.Fatal(err)
	}
	f, err := os.CreateTemp(t.TempDir(), "leak")
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	if err := os.Remove(f.Name()); err != nil {
		t.Fatal(err)
	}
	_, afterBytes, _, afterFiles, err := fdInventory()
	if err != nil {
		t.Fatal(err)
	}
	if afterFiles != files+1 || afterBytes != bytes {
		t.Fatalf("empty leak not counted: %d/%d -> %d/%d", files, bytes, afterFiles, afterBytes)
	}
}
