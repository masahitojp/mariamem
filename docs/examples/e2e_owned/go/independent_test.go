package ownedexample

import (
	"io"
	"net/http"
	"net/url"
	"os"
	"strings"
	"testing"

	"github.com/masahitojp/mariamem/mariamemtest"
)

func TestOwnedIndependentOwners(t *testing.T) {
	if os.Getenv("E2E_OWNED_RUNTIME") != "1" {
		t.Skip("explicit owned runtime only")
	}
	owners := []*mariamemtest.HTTPFixture{}
	for i := 0; i < 2; i++ {
		owners = append(owners, mariamemtest.NewHTTP(t, mariamemtest.HTTPConfig{
			Prepare: prepare, StartReady: start, SoleWorkSource: true,
		}))
	}
	read := func(t *testing.T, response *http.Response, err error) string {
		t.Helper()
		if err != nil {
			t.Fatal(err)
		}
		defer response.Body.Close()
		body, err := io.ReadAll(response.Body)
		if err != nil || response.StatusCode != 200 {
			t.Fatalf("HTTP: %v %d %s", err, response.StatusCode, body)
		}
		return string(body)
	}
	seed := func(t *testing.T, c *mariamemtest.HTTPCase) {
		t.Helper()
		response, err := c.Client.Get(c.BaseURL + "/orders")
		body := read(t, response, err)
		if !strings.Contains(body, "SEED:2:ready") || strings.Contains(body, "NEW:3:ready") {
			t.Fatal("seed or cross-owner isolation", body)
		}
	}
	identities, urls := make([]string, 2), make([]string, 2)
	for round, pair := range [][2]int{{0, 1}, {1, 0}} {
		t.Run([]string{"forward", "reverse"}[round], func(t *testing.T) {
			left := owners[pair[0]].Case(t)
			seed(t, left)
			response, err := left.Client.PostForm(left.BaseURL+"/orders", url.Values{"sku": {"NEW"}, "quantity": {"3"}})
			if !strings.Contains(read(t, response, err), "NEW:3:ready") {
				t.Fatal("mutation absent")
			}
			t.Run("independent", func(t *testing.T) {
				right := owners[pair[1]].Case(t)
				seed(t, right)
				if left.App.Identity() == right.App.Identity() || left.BaseURL == right.BaseURL {
					t.Fatal("shared app")
				}
				for i, c := range []*mariamemtest.HTTPCase{left, right} {
					index := pair[i]
					if round == 0 {
						identities[index], urls[index] = c.App.Identity(), c.BaseURL
					} else if identities[index] != c.App.Identity() || urls[index] != c.BaseURL {
						t.Fatal("app restarted")
					}
				}
			})
			response, err = left.Client.Get(left.BaseURL + "/orders")
			if !strings.Contains(read(t, response, err), "NEW:3:ready") {
				t.Fatal("other owner reset active case")
			}
		})
	}
}
