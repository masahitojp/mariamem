/* Experimental UCA1400 default data copy. Kept private to this source file. */
static int
mariamem_uca_copy_default(MY_CHARSET_LOADER *loader, CHARSET_INFO *cs,
                          MY_COLL_RULES *rules, MY_UCA_WEIGHT_LEVEL *dst,
                          const MY_UCA_WEIGHT_LEVEL *src)
{
  uint id= cs->number, level= src->levelno, encoding;
  MY_CONTRACTION *items, *hash;
  char *flags;
  size_t item_bytes;
  if (!(id == 2048 || id == 2304 || id == 2560 ||
        id == 2816 || id == 3072) ||
      !cs->tailoring || cs->tailoring[0] || rules->nrules || level >= 3)
    return 0;
  encoding= my_uca1400_collation_id_to_charset_id(id);
  if (src != &my_uca_v1400.level[level] ||
      dst != &my_uca1400_info_tailored[encoding][0].level[level] ||
      src->maxchar != 0x10FFFF || src->contractions.nitems != 939)
    return 0;
  item_bytes= src->contractions.nitems * sizeof(MY_CONTRACTION);
  items= (MY_CONTRACTION*) loader->once_alloc(item_bytes);
  if (!items) return -1;
  flags= (char*) loader->once_alloc(MY_UCA_CNT_FLAG_SIZE);
  if (!flags) return -1;
  hash= (MY_CONTRACTION*) loader->once_alloc(
          MY_UCA_CONTRACTION_HASH_ALLOC_ELEMENTS * sizeof(MY_CONTRACTION));
  if (!hash) return -1;
  memcpy(items, src->contractions.item, item_bytes);
  memcpy(flags, mariamem_uca_copy_flags[level], MY_UCA_CNT_FLAG_SIZE);
  memcpy(hash, mariamem_uca_copy_hash[level],
         MY_UCA_CONTRACTION_HASH_ALLOC_ELEMENTS * sizeof(MY_CONTRACTION));
  /* Publish payload pointers/counts only when all allocations/copies succeed. */
  dst->contractions.item= items;
  dst->contractions.flags= flags;
  dst->contractions.nitems= src->contractions.nitems;
  dst->contraction_hash.item= hash;
  dst->contraction_hash.nitems_alloced= MY_UCA_CONTRACTION_HASH_ALLOC_ELEMENTS;
  if (getenv("MARIAMEM_UCA_COPY_VERIFY_INTERNAL"))
  {
    MY_CONTRACTIONS original= {0};
    MY_UCA_CONTRACTION_HASH original_hash= {0};
    size_t i;
    if (my_uca_alloc_contractions(&original, loader, src->contractions.nitems))
      abort();
    for (i= 0; i != src->contractions.nitems; i++)
    {
      MY_CONTRACTION *item= &src->contractions.item[i];
      size_t length= my_wstrnlen(item->ch, array_elements(item->ch));
      uint16 *weights= my_uca_init_one_contraction(&original, item->ch,
                                                  length, item->with_context);
      memcpy(weights, item->weight, sizeof(item->weight));
    }
    if (my_uca_contraction_hash_allocate(&original_hash, loader) ||
        my_uca_contraction_hash_populate(&original_hash, &original) ||
        memcmp(items, original.item, item_bytes) ||
        memcmp(flags, original.flags, MY_UCA_CNT_FLAG_SIZE) ||
        memcmp(hash, original_hash.item,
               MY_UCA_CONTRACTION_HASH_ALLOC_ELEMENTS * sizeof(MY_CONTRACTION)))
      abort();
    fprintf(stderr, "UCA_COPY_VERIFY id=%u level=%u match=1\n", id, level);
  }
  return 1;
}
