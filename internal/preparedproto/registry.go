package preparedproto

import "errors"

var ErrStatement = errors.New("invalid prepared statement ownership or metadata")

// Entry belongs to one physical session, not a logical pooled database handle.
type Entry struct {
	Handle     uint32
	Parameters uint16
}

// Registry is owned by one serial session dispatcher, not shared concurrently.
type Registry struct {
	generation uint32
	next       uint32
	entries    map[uint32]Entry
	handles    map[uint32]uint32
}

func NewRegistry(generation uint32) (*Registry, error) {
	if generation == 0 {
		return nil, ErrStatement
	}
	return &Registry{generation: generation, entries: make(map[uint32]Entry), handles: make(map[uint32]uint32)}, nil
}
func (r *Registry) Generation() uint32 { return r.generation }

// Add is transactional: rejected metadata never leaves a partially owned entry.
func (r *Registry) Add(generation, handle, parameters uint32) (uint32, error) {
	if generation != r.generation || handle == 0 || parameters > 65535 || r.next == ^uint32(0) {
		return 0, ErrStatement
	}
	if _, exists := r.handles[handle]; exists {
		return 0, ErrStatement
	}
	r.next++
	id := r.next
	r.entries[id] = Entry{handle, uint16(parameters)}
	r.handles[handle] = id
	return id, nil
}
func (r *Registry) Lookup(id uint32) (Entry, bool) { e, ok := r.entries[id]; return e, ok }
func (r *Registry) Remove(id uint32) {
	if e, ok := r.entries[id]; ok {
		delete(r.handles, e.Handle)
		delete(r.entries, id)
	}
}

// Clear invalidates host mappings; guest session shutdown owns native destruction.
func (r *Registry) Clear() { clear(r.entries); clear(r.handles) }
