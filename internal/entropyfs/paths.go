// Package entropyfs provides only the two guest entropy devices, never a host root.
package entropyfs

func allowed(name string) bool { return name == "/dev/urandom" || name == "/dev/random" }
