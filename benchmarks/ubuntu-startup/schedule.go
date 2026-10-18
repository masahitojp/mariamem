package main

import "sync"

// runChildren preserves the per-child workload. Barrier mode delays use until
// all children are ready; require one worker per child to avoid pool deadlock.
func runChildren(n, workers int, barrier bool, start, use func(int), allReady func()) {
	if n < 1 || workers < 1 || (barrier && workers != n) {
		panic("invalid child scheduling dimensions")
	}
	var ready, finished sync.WaitGroup
	ready.Add(n)
	jobs := make(chan int)
	release := make(chan struct{})
	for w := 0; w < workers; w++ {
		finished.Add(1)
		go func() {
			defer finished.Done()
			for i := range jobs {
				start(i)
				ready.Done()
				if barrier {
					<-release
				}
				use(i)
			}
		}()
	}
	for i := 0; i < n; i++ {
		jobs <- i
	}
	close(jobs)
	ready.Wait()
	allReady()
	close(release)
	finished.Wait()
}
