package store_test

import (
	"fmt"
	"strings"
	"testing"

	"github.com/shibukawa/pgmem/bench/modelcase/store"
)

// Each read-only scenario is a table of ten cases; every case is its own
// test on the shared database.

func TestListOrders(t *testing.T) {
	fx.Group(t, false)
	sample := store.SampleOrders()
	for _, want := range sample[:10] {
		t.Run(fmt.Sprintf("user_%d", want.UserID), func(t *testing.T) {
			db := fx.Read(t)
			got, err := store.ListOrders(t.Context(), db, want.UserID)
			if err != nil {
				t.Fatal(err)
			}
			var expected int
			for _, o := range sample {
				if o.UserID == want.UserID {
					expected++
				}
			}
			if len(got) != expected {
				t.Fatalf("%d orders, want %d", len(got), expected)
			}
			var found bool
			for _, s := range got {
				if s.ID == want.ID {
					found = true
					if s.ItemCount != len(want.Items) {
						t.Errorf("order %d: %d items, want %d", s.ID, s.ItemCount, len(want.Items))
					}
				}
			}
			if !found {
				t.Errorf("order %d missing", want.ID)
			}
		})
	}
}

func TestGetOrder(t *testing.T) {
	fx.Group(t, false)
	sample := store.SampleOrders()
	for n := 1; n <= 10; n++ {
		t.Run(fmt.Sprintf("orders_%d_%d_%d_%d", n, n+10, n+20, n+30), func(t *testing.T) {
			db := fx.Read(t)
			for _, id := range []int{n, n + 10, n + 20, n + 30} {
				want := sample[id-1]
				got, err := store.GetOrder(t.Context(), db, want.ID)
				if err != nil {
					t.Fatal(err)
				}
				var total int64
				for _, it := range want.Items {
					total += int64(it.Quantity) * it.UnitPriceCents
				}
				if got.TotalCents != total || got.Status != want.Status || len(got.Items) != len(want.Items) {
					t.Errorf("order %d: got %+v", want.ID, got)
				}
			}
			if n == 1 {
				if _, err := store.GetOrder(t.Context(), db, 999999); err != store.ErrNotFound {
					t.Errorf("missing order: %v", err)
				}
			}
		})
	}
}

func TestTopProducts(t *testing.T) {
	fx.Group(t, false)
	sold := map[int64]int64{}
	for _, o := range store.SampleOrders() {
		if o.Status == "cancelled" {
			continue
		}
		for _, it := range o.Items {
			sold[it.ProductID] += int64(it.Quantity)
		}
	}
	for _, n := range []int{1, 2, 3, 5, 8, 10, 15, 20, 30, 50} {
		t.Run(fmt.Sprintf("top_%d", n), func(t *testing.T) {
			db := fx.Read(t)
			got, err := store.TopProducts(t.Context(), db, n)
			if err != nil {
				t.Fatal(err)
			}
			if want := min(n, len(sold)); len(got) != want {
				t.Fatalf("got %d rows, want %d", len(got), want)
			}
			for i, p := range got {
				if i > 0 && p.Quantity > got[i-1].Quantity {
					t.Errorf("not sorted at %d", i)
				}
				if sold[p.ProductID] != p.Quantity {
					t.Errorf("product %d: %d sold, want %d", p.ProductID, p.Quantity, sold[p.ProductID])
				}
			}
		})
	}
}

func TestSearchProducts(t *testing.T) {
	fx.Group(t, false)
	for d := 0; d <= 9; d++ {
		prefix := fmt.Sprintf("product %d", d)
		t.Run(strings.ReplaceAll(prefix, " ", "_"), func(t *testing.T) {
			db := fx.Read(t)
			got, err := store.SearchProducts(t.Context(), db, prefix)
			if err != nil {
				t.Fatal(err)
			}
			var matches int
			for i := 1; i <= store.MasterProducts; i++ {
				if strings.HasPrefix(strings.ToLower(fmt.Sprintf("Product %d", i)), prefix) {
					matches++
				}
			}
			if want := min(matches, 50); len(got) != want {
				t.Fatalf("got %d rows, want %d", len(got), want)
			}
			for _, p := range got {
				if !strings.HasPrefix(strings.ToLower(p.Name), prefix) {
					t.Errorf("unexpected %q", p.Name)
				}
			}
		})
	}
}

func TestRevenueByCategory(t *testing.T) {
	fx.Group(t, false)
	// category of a product is 1 + id % 20, as SeedMaster inserts them
	want := map[int]int64{}
	for _, o := range store.SampleOrders() {
		if o.Status != "paid" && o.Status != "shipped" {
			continue
		}
		for _, it := range o.Items {
			want[1+int(it.ProductID)%store.MasterCategories] += int64(it.Quantity) * it.UnitPriceCents
		}
	}
	names := []string{"Books", "Music", "Movies", "Games", "Toys", "Garden", "Kitchen", "Tools", "Sports", "Outdoors"}
	for i, name := range names {
		category := i + 1
		t.Run(name, func(t *testing.T) {
			db := fx.Read(t)
			got, err := store.RevenueByCategory(t.Context(), db)
			if err != nil {
				t.Fatal(err)
			}
			if len(got) != store.MasterCategories {
				t.Fatalf("got %d categories", len(got))
			}
			for _, r := range got {
				if r.Category == name && r.RevenueCents != want[category] {
					t.Errorf("%s: revenue %d, want %d", name, r.RevenueCents, want[category])
				}
			}
		})
	}
}
