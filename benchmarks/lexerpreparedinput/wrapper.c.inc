static my_bool mariamem_init_compiled_state_maps(struct charset_info_st *cs)
{
  const uchar *pair;
  /* This wrapper is called only by the pre-XML compiled registration loop.
     Mutable/loaded descriptors and unknown IDs retain the original producer. */
  if (!(cs->state & MY_CS_COMPILED) ||
      !(pair= mariamem_lexer_lookup(cs->number)) ||
      getenv("MARIAMEM_LEXER_ORIGINAL_INTERNAL"))
    return init_state_maps(cs);
  if (getenv("MARIAMEM_LEXER_VERIFY_INTERNAL"))
  {
    if (init_state_maps(cs))
      abort();
    int match= !memcmp(cs->state_map, pair, 256) &&
               !memcmp(cs->ident_map, pair + 256, 256);
    fprintf(stderr, "LEXER_PREPARED_VERIFY id=%u bytes=512 match=%d\n", cs->number, match);
    if (!match)
      abort();
  }
  cs->state_map= pair;
  cs->ident_map= pair + 256;
  return 0;
}
