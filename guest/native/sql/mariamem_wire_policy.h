// The local native profile constrains already-decoded values. No wire parser,
// parameter registry, transport state or response serializer belongs here.
#ifndef MARIAMEM_WIRE_POLICY_H
#define MARIAMEM_WIRE_POLICY_H
#include <stddef.h>
#include <stdint.h>
static inline bool mariamem_wire_command_allowed(unsigned command)
{
  switch (command) {
  case 1: case 2: case 3: case 14: case 22:
  case 23: case 24: case 25: case 26: case 27:
    return true;
  default:
    return false;
  }
}
static inline bool mariamem_wire_handshake_allowed(uint64_t flags)
{
  // Require PROTOCOL_41; reject SSL before server/client capability intersection.
  // Other unadvertised extension bits retain their existing masked behavior.
  return (flags & 512U) != 0 && (flags & 2048U) == 0;
}
static inline bool mariamem_wire_output_allowed(size_t payload)
{
  // A logical packet may never enter upstream continuation framing.
  return payload <= 0xfffffeUL;
}
#endif
