package store_test

import (
	"fmt"
	"testing"

	"github.com/shibukawa/pgmem/bench/modelcase/store"
)

// Each writing scenario is a table of four cases; every case is its own
// test on its own copy of the data (pgmem) or on the reset shared database.

func TestCreateOrder(t *testing.T) {
	fx.Group(t, true)
	cases := []struct {
		name   string
		userID int64
		items  []store.OrderItem
		fails  bool
	}{
		{"two_lines", 1, []store.OrderItem{{ProductID: 1, Quantity: 2}, {ProductID: 2, Quantity: 1}}, false},
		{"one_line", 2, []store.OrderItem{{ProductID: 3, Quantity: 5}}, false},
		{"five_lines", 3, []store.OrderItem{{ProductID: 10, Quantity: 1}, {ProductID: 11, Quantity: 1}, {ProductID: 12, Quantity: 1}, {ProductID: 13, Quantity: 1}, {ProductID: 14, Quantity: 1}}, false},
		{"out_of_stock", 4, []store.OrderItem{{ProductID: 5, Quantity: 1000}}, true},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			db := fx.Write(t)
			ctx := t.Context()
			id, err := store.CreateOrder(ctx, db, tc.userID, tc.items)
			if tc.fails {
				if err == nil {
					t.Fatal("oversold")
				}
				return
			}
			if err != nil {
				t.Fatal(err)
			}
			got, err := store.GetOrder(ctx, db, id)
			if err != nil {
				t.Fatal(err)
			}
			var total int64
			for _, it := range tc.items {
				total += int64(it.Quantity) * (500 + (it.ProductID*37)%20000)
			}
			if got.Status != "pending" || len(got.Items) != len(tc.items) || got.TotalCents != total {
				t.Fatalf("got %+v, want total %d (trigger)", got, total)
			}
			var stock int
			if err := db.QueryRowContext(ctx, `SELECT stock FROM products WHERE id = $1`, tc.items[0].ProductID).Scan(&stock); err != nil {
				t.Fatal(err)
			}
			if stock >= 100 {
				t.Errorf("stock not reserved: %d", stock)
			}
		})
	}
}

func TestCancelOrder(t *testing.T) {
	fx.Group(t, true)
	sample := store.SampleOrders()
	byStatus := func(status string, nth int) store.SampleOrder {
		for _, o := range sample {
			if o.Status == status {
				if nth == 0 {
					return o
				}
				nth--
			}
		}
		t.Fatalf("no %s order", status)
		return store.SampleOrder{}
	}
	cases := []struct {
		name  string
		order store.SampleOrder
		fails bool
	}{
		{"paid", byStatus("paid", 0), false},
		{"pending", byStatus("pending", 0), false},
		{"another_paid", byStatus("paid", 3), false},
		{"shipped", byStatus("shipped", 0), true},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			db := fx.Write(t)
			ctx := t.Context()
			o := tc.order
			var before int
			if err := db.QueryRowContext(ctx, `SELECT stock FROM products WHERE id = $1`, o.Items[0].ProductID).Scan(&before); err != nil {
				t.Fatal(err)
			}
			err := store.CancelOrder(ctx, db, o.ID)
			if tc.fails {
				if err != store.ErrNotFound {
					t.Fatalf("cancelled a shipped order: %v", err)
				}
				return
			}
			if err != nil {
				t.Fatal(err)
			}
			got, err := store.GetOrder(ctx, db, o.ID)
			if err != nil {
				t.Fatal(err)
			}
			if got.Status != "cancelled" {
				t.Errorf("status %q", got.Status)
			}
			var after, audits int
			if err := db.QueryRowContext(ctx, `SELECT stock FROM products WHERE id = $1`, o.Items[0].ProductID).Scan(&after); err != nil {
				t.Fatal(err)
			}
			if after != before+o.Items[0].Quantity {
				t.Errorf("stock %d, want %d", after, before+o.Items[0].Quantity)
			}
			if err := db.QueryRowContext(ctx, `SELECT count(*) FROM audit_log WHERE order_id = $1 AND new_status = 'cancelled'`, o.ID).Scan(&audits); err != nil {
				t.Fatal(err)
			}
			if audits != 1 {
				t.Errorf("%d audit rows", audits)
			}
			if err := store.CancelOrder(ctx, db, o.ID); err != store.ErrNotFound {
				t.Errorf("second cancel: %v", err)
			}
		})
	}
}

func TestShipOrder(t *testing.T) {
	fx.Group(t, true)
	sample := store.SampleOrders()
	var paid, pending []int64
	for _, o := range sample {
		switch o.Status {
		case "paid":
			paid = append(paid, o.ID)
		case "pending":
			pending = append(pending, o.ID)
		}
	}
	t.Run("one_paid", func(t *testing.T) {
		db := fx.Write(t)
		if err := store.ShipOrder(t.Context(), db, paid[0]); err != nil {
			t.Fatal(err)
		}
		got, err := store.GetOrder(t.Context(), db, paid[0])
		if err != nil || got.Status != "shipped" {
			t.Fatalf("%+v %v", got, err)
		}
	})
	t.Run("pending_rejected", func(t *testing.T) {
		db := fx.Write(t)
		if err := store.ShipOrder(t.Context(), db, pending[0]); err != store.ErrNotFound {
			t.Fatalf("shipped a pending order: %v", err)
		}
	})
	t.Run("all_paid", func(t *testing.T) {
		db := fx.Write(t)
		for _, id := range paid {
			if err := store.ShipOrder(t.Context(), db, id); err != nil {
				t.Fatal(err)
			}
		}
		var shipped, wasShipped int
		for _, o := range sample {
			if o.Status == "shipped" {
				wasShipped++
			}
		}
		if err := db.QueryRowContext(t.Context(), `SELECT count(*) FROM orders WHERE status = 'shipped'`).Scan(&shipped); err != nil {
			t.Fatal(err)
		}
		if shipped != len(paid)+wasShipped {
			t.Errorf("%d shipped, want %d", shipped, len(paid)+wasShipped)
		}
	})
	t.Run("twice", func(t *testing.T) {
		db := fx.Write(t)
		if err := store.ShipOrder(t.Context(), db, paid[1]); err != nil {
			t.Fatal(err)
		}
		if err := store.ShipOrder(t.Context(), db, paid[1]); err != store.ErrNotFound {
			t.Fatalf("shipped twice: %v", err)
		}
		var audits int
		if err := db.QueryRowContext(t.Context(), `SELECT count(*) FROM audit_log WHERE order_id = $1`, paid[1]).Scan(&audits); err != nil {
			t.Fatal(err)
		}
		if audits != 2 { // insert + one status change
			t.Errorf("%d audit rows", audits)
		}
	})
}

func TestDeleteUser(t *testing.T) {
	fx.Group(t, true)
	sample := store.SampleOrders()
	for _, o := range sample[1:5] {
		t.Run(fmt.Sprintf("user_%d", o.UserID), func(t *testing.T) {
			db := fx.Write(t)
			ctx := t.Context()
			if err := store.DeleteUser(ctx, db, o.UserID); err != nil {
				t.Fatal(err)
			}
			for _, other := range sample {
				if other.UserID != o.UserID {
					continue
				}
				if _, err := store.GetOrder(ctx, db, other.ID); err != store.ErrNotFound {
					t.Errorf("order %d survived its user: %v", other.ID, err)
				}
				var items int
				if err := db.QueryRowContext(ctx, `SELECT count(*) FROM order_items WHERE order_id = $1`, other.ID).Scan(&items); err != nil {
					t.Fatal(err)
				}
				if items != 0 {
					t.Errorf("%d orphan items", items)
				}
			}
			if err := store.DeleteUser(ctx, db, o.UserID); err != store.ErrNotFound {
				t.Errorf("second delete: %v", err)
			}
		})
	}
}

func TestApplyDiscount(t *testing.T) {
	fx.Group(t, true)
	cases := []struct {
		name     string
		category int
		percent  int
	}{
		{"books_10", 1, 10},
		{"music_25", 2, 25},
		{"movies_50", 3, 50},
		{"games_0", 4, 0},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			db := fx.Write(t)
			ctx := t.Context()
			n, err := store.ApplyDiscount(ctx, db, tc.category, tc.percent)
			if err != nil {
				t.Fatal(err)
			}
			if n != store.MasterProducts/store.MasterCategories {
				t.Errorf("%d products changed", n)
			}
			// product id with id % 20 == category - 1 belongs to the category
			pid := int64(20 + tc.category - 1)
			var price int64
			if err := db.QueryRowContext(ctx, `SELECT price_cents FROM products WHERE id = $1`, pid).Scan(&price); err != nil {
				t.Fatal(err)
			}
			if want := (500 + pid*37%20000) * int64(100-tc.percent) / 100; price != want {
				t.Errorf("price %d, want %d", price, want)
			}
			// existing order lines keep the price they were sold at
			o, err := store.GetOrder(ctx, db, 1)
			if err != nil {
				t.Fatal(err)
			}
			for _, it := range o.Items {
				if want := 500 + (it.ProductID*37)%20000; it.UnitPriceCents != want {
					t.Errorf("line price changed: %+v", it)
				}
			}
		})
	}
}
