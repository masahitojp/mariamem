package main

import (
	"context"
	"os"

	"github.com/jackc/pgx/v5"
	"github.com/shibukawa/pgmem"
)

// pgmemTarget runs the library in this process, the way Go tests use it.
// Host memory is this process's phys_footprint growth; RSS is reported
// separately for reference, so the idle harness itself is subtracted.
type pgmemTarget struct {
	s       *pgmem.Server
	snap    *pgmem.Snapshot
	baseRSS float64
	baseFP  float64
}

func (p *pgmemTarget) start(ctx context.Context) error {
	var err error
	if p.baseRSS, err = rssMB(ctx, os.Getpid()); err != nil {
		return err
	}
	if p.baseFP, err = footprintMB(ctx, os.Getpid()); err != nil {
		return err
	}
	p.s, err = pgmem.Start(ctx, pgmem.Options{Database: "app"})
	if err != nil {
		return err
	}
	return waitReady(ctx, p.url())
}

func (p *pgmemTarget) url() string { return p.s.DSN() }

func (p *pgmemTarget) prepareIsolation(ctx context.Context) error {
	var err error
	p.snap, err = p.s.Snapshot(ctx, pgmem.SnapshotOptions{})
	return err
}

func (p *pgmemTarget) isolate(ctx context.Context, fn func(string) error) error {
	f, err := p.snap.Fork(ctx)
	if err != nil {
		return err
	}
	defer f.Close()
	return fn(f.DSN())
}

// mem is the growth of this process, where the server runs.
func (p *pgmemTarget) mem(ctx context.Context) (memory, error) {
	rss, err := rssMB(ctx, os.Getpid())
	if err != nil {
		return memory{}, err
	}
	fp, err := footprintMB(ctx, os.Getpid())
	growth := fp - p.baseFP
	return memory{Host: growth, RSS: rss - p.baseRSS, Process: growth, Service: growth}, err
}

func (p *pgmemTarget) dialQuery(ctx context.Context) (float64, error) {
	cfg, err := pgx.ParseConfig(p.s.DSN())
	if err != nil {
		return 0, err
	}
	cfg.DialFunc = p.s.Dial
	conn, err := pgx.ConnectConfig(ctx, cfg)
	if err != nil {
		return 0, err
	}
	defer conn.Close(ctx)
	return simpleQuery(ctx, conn)
}

func (p *pgmemTarget) stop(context.Context) {
	if p.snap != nil {
		p.snap.Close()
	}
	if p.s != nil {
		p.s.Close()
	}
}
