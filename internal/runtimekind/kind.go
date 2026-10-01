// Package runtimekind describes internal execution identity, never a public option.
package runtimekind

type Kind string

const GeneratedGo Kind = "generated-go"
const Wasmer Kind = "wasmer"
const GuestSHA256 = "5a513f74607ef1f1ddd4a36ebeefbba50354d9d00564e1977475d642104903bb"
