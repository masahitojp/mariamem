package guest

import (
	"context"
	"errors"
	"github.com/masahitojp/mariamem/internal/preparedproto"
	"strings"
	"testing"
)

func TestPreparedEnvelopeBudgetDoesNotIncreaseTextSQLBudget(t *testing.T) {
	stopped := errors.New("test process stopped")
	p := &Process{failure: stopped}
	body := make([]byte, (1<<20)+preparedproto.HeaderSize)
	if _, e := p.Call(context.Background(), 2, 0, body); e == nil || !strings.Contains(e.Error(), "payload limit") {
		t.Fatal("text limit changed", e)
	}
	if _, e := p.Call(context.Background(), preparedproto.GuestOpcode, 0, body); !errors.Is(e, stopped) {
		t.Fatal("prepared SQL envelope overhead rejected", e)
	}
	large := make([]byte, preparedproto.MaxEnvelope+1)
	if _, e := p.Call(context.Background(), preparedproto.GuestOpcode, 0, large); e == nil || !strings.Contains(e.Error(), "payload limit") {
		t.Fatal("internal limit lost", e)
	}
}
