### canonical patched mysys/my_largepage.c:430-465
```c
  more memory later.
  Every implementation returns a zero filled buffer here.
*/
#if defined(__EMSCRIPTEN__) || defined(__wasi__)
/* WASM reservations are committed and zero-filled; preserve free(ptr). */
char *my_large_virtual_alloc_aligned(size_t *size, size_t alignment)
{
  void *p= NULL;
  DBUG_ENTER("my_large_virtual_alloc_aligned");
  if (posix_memalign(&p, alignment, *size))
    DBUG_RETURN(NULL);
  memset(p, 0, *size);
  DBUG_RETURN((char *) p);
}
#endif

char *my_large_virtual_alloc(size_t *size)
{
  char *ptr;
  DBUG_ENTER("my_large_virtual_alloc");

#if defined(__EMSCRIPTEN__) || defined(__wasi__)
  DBUG_RETURN(my_large_virtual_alloc_aligned(size, 4096));
#endif

  if (my_use_large_pages)
  {
    size_t large_page_size;
    int page_i= 0;

    while ((large_page_size= my_next_large_page_size(*size, &page_i)) != 0)
    {
      int mapflag= MAP_PRIVATE |
# ifdef MAP_POPULATE
        MAP_POPULATE |
# endif
```

### canonical patched mysys/my_virtual_mem.c:70-108
```c
#endif

/*
  "commit" - in other words, allocate - memory.
  ptr must lie within a previously reserved range or be NULL.
  in the latter case new memory is reserved and committed.

  This is compatible with the mmap / VirtualAlloc semantics.
*/
char *my_virtual_mem_commit(char *ptr, size_t size)
{
#if defined(__EMSCRIPTEN__) || defined(__wasi__)
  /* Preserve the NULL allocation contract without unsupported mmap flags. */
  if (!ptr)
  {
    void *p= NULL;
    if (posix_memalign(&p, 4096, size))
      return NULL;
    memset(p, 0, size);
    ptr= p;
  }
  update_malloc_size(size, 0);
  return ptr;
#elif defined(_WIN32)
  if (!ptr)
    return VirtualAlloc(NULL, size, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
  if (my_use_large_pages)
  {
    DBUG_ASSERT(is_memory_committed(ptr, size));
  }
  else
  {
    void *p= VirtualAlloc(ptr, size, MEM_COMMIT, PAGE_READWRITE);
    DBUG_ASSERT(p == ptr);
    if (!p)
    {
      my_error(EE_OUTOFMEMORY, MYF(ME_BELL + ME_ERROR_LOG), size);
      return NULL;
    }
```

### canonical patched mysys/my_virtual_mem.c:150-215
```c
# endif
  }
#endif
  update_malloc_size(size, 0);
  return ptr;
}

void my_virtual_mem_decommit(char *ptr, size_t size)
{
#if defined(__EMSCRIPTEN__) || defined(__wasi__)
  (void) ptr;
  update_malloc_size(-(longlong) size, 0);
  return;
#elif defined(_WIN32)
  DBUG_ASSERT(is_memory_committed(ptr, size));
  if (!my_use_large_pages)
  {
    if (!VirtualFree(ptr, size, MEM_DECOMMIT))
    {
      my_error(EE_BADMEMORYRELEASE, MYF(ME_ERROR_LOG_ONLY), ptr, size,
               GetLastError());
      DBUG_ASSERT(0);
    }
  }
#else
# ifdef _AIX
  disclaim(ptr, size, DISCLAIM_ZEROMEM);
# elif defined __linux__ || defined __osf__
  madvise(ptr, size, MADV_DONTNEED); /* OSF/1, Linux mimicing AIX disclaim() */
# elif defined MADV_FREE_REUSABLE && defined MADV_FREE_REUSE
  /* Mac OS X 10.9; undocumented in Apple macOS */
  madvise(ptr, size, MADV_FREE_REUSABLE); /* macOS mimicing AIX disclaim() */
# elif defined MADV_PURGE /* Illumos */
  madvise(ptr, size, MADV_PURGE); /* Illumos mimicing AIX disclaim() */
# elif defined MADV_FREE
  /* FreeBSD, NetBSD, OpenBSD, Dragonfly BSD, OpenSolaris, Apple macOS */
  madvise(ptr, size, MADV_FREE); /* allow lazy zeroing out */
# elif defined MADV_DONTNEED
#  warning "It is unclear if madvise(MADV_DONTNEED) works as intended"
  madvise(ptr, size, MADV_DONTNEED);
# else
#  warning "Do not know how to decommit memory"
# endif
  if (mprotect(ptr, size, PROT_NONE))
  {
    my_error(EE_BADMEMORYRELEASE, MYF(ME_ERROR_LOG_ONLY), ptr, size, errno);
    DBUG_ASSERT(0);
  }
#endif
  update_malloc_size(-(longlong) size, 0);
}

void my_virtual_mem_release(char *ptr, size_t size)
{
#if defined(__EMSCRIPTEN__) || defined(__wasi__)
  free(ptr);
  return;
#elif defined(_WIN32)
  if (!VirtualFree(ptr, 0, MEM_RELEASE))
  {
    my_error(EE_BADMEMORYRELEASE, MYF(ME_ERROR_LOG_ONLY), ptr, size,
             GetLastError());
    DBUG_ASSERT(0);
  }
#else
  if (munmap(ptr, size))
```

### canonical patched storage/innobase/buf/buf0buf.cc:1470-1500
```c
#endif /* HAVE_LIBNUMA */

  n_blocks= get_n_blocks(actual_size);
  n_blocks_to_withdraw= 0;
  UT_LIST_INIT(free, &buf_page_t::list);
  const size_t ssize= srv_page_size_shift - UNIV_PAGE_SIZE_SHIFT_MIN;

  for (char *extent= memory,
         *end= memory + block_descriptors_in_bytes(n_blocks);
       extent < end; extent+= innodb_buffer_pool_extent_size)
  {
    buf_block_t *block= reinterpret_cast<buf_block_t*>(extent);
    const buf_block_t *extent_end= block + pages_in_extent[ssize];
    if (reinterpret_cast<const char*>(extent_end) > end)
      extent_end= reinterpret_cast<buf_block_t*>(end);
    MEM_MAKE_DEFINED(block, (extent_end - block) * sizeof *block);
    for (byte *frame= reinterpret_cast<byte*>(extent) +
           first_frame_in_extent[ssize];
         block < extent_end; block++, frame+= srv_page_size)
    {
      ut_ad(!memcmp(block, field_ref_zero, sizeof *block));
      block->page.frame= frame;
      block->page.lock.init();
      UT_LIST_ADD_LAST(free, &block->page);
      ut_d(block->page.in_free_list= true);
    }
  }

  UT_LIST_INIT(withdrawn, &buf_page_t::list);
  UT_LIST_INIT(LRU, &buf_page_t::LRU);
  UT_LIST_INIT(flush_list, &buf_page_t::list);
```

### canonical patched storage/innobase/buf/buf0buf.cc:1990-2070
```c
  const ssize_t n_blocks_removed= n_blocks - n_blocks_new;

  if (n_blocks_removed <= 0)
  {
    if (!my_virtual_mem_commit(memory + old_size, size - old_size))
    {
      mysql_mutex_unlock(&mutex);
      sql_print_error("InnoDB: Cannot commit innodb_buffer_pool_size=%zum;"
                      " retaining innodb_buffer_pool_size=%zum",
                      size >> 20, old_size >> 20);
      my_error(ER_OUT_OF_RESOURCES, MYF(0));
      return;
    }

    size_in_bytes_requested= size;
    size_in_bytes= size;
#if defined __linux__ || defined __FreeBSD__
    core_advise();
#endif

    {
      const size_t ssize= srv_page_size_shift - UNIV_PAGE_SIZE_SHIFT_MIN;
      const size_t pages= pages_in_extent[ssize];
      const size_t first_extent= n_blocks / pages;

      char *extent= memory + first_extent * innodb_buffer_pool_extent_size;

      buf_block_t *block= reinterpret_cast<buf_block_t*>(extent);
      if (const size_t first_blocks= n_blocks % pages)
      {
        /* Extend the last (partial) extent until its end */
        const buf_block_t *extent_end= block +
          (first_extent == (n_blocks_new / pages)
           ? (n_blocks_new % pages)
           : pages);
        block+= first_blocks;
        memset((void*) block, 0, (extent_end - block) * sizeof *block);

        for (byte *frame= reinterpret_cast<byte*>(extent) +
               first_frame_in_extent[ssize] +
               (first_blocks << srv_page_size_shift); block < extent_end;
             block++, frame+= srv_page_size)
        {
          block->page.frame= frame;
          block->page.lock.init();
          UT_LIST_ADD_LAST(free, &block->page);
          ut_d(block->page.in_free_list= true);
        }
        extent+= innodb_buffer_pool_extent_size;
      }

      /* Fill in further extents; @see buf_pool_t::create() */
      for (const char *const end_new= memory +
             block_descriptors_in_bytes(n_blocks_new);
           extent < end_new; extent+= innodb_buffer_pool_extent_size)
      {
        block= reinterpret_cast<buf_block_t*>(extent);
        const buf_block_t *extent_end= block + pages;
        if (reinterpret_cast<const char*>(extent_end) > end_new)
          extent_end= reinterpret_cast<const buf_block_t*>(end_new);

        memset((void*) block, 0, (extent_end - block) * sizeof *block);
        for (byte *frame= reinterpret_cast<byte*>(extent) +
               first_frame_in_extent[ssize];
             block < extent_end; block++, frame+= srv_page_size)
        {
          block->page.frame= frame;
          block->page.lock.init();
          UT_LIST_ADD_LAST(free, &block->page);
          ut_d(block->page.in_free_list= true);
        }
      }
    }

    mysql_mutex_unlock(&LOCK_global_system_variables);
  resized:
    ut_ad(UT_LIST_GET_LEN(withdrawn) == 0);
    ut_ad(n_blocks_to_withdraw == 0);
    ut_ad(!first_to_withdraw);
    const size_t old_blocks{n_blocks};
    n_blocks= n_blocks_new;
```

### canonical patched storage/innobase/buf/buf0buf.cc:1605-1630
```c
         extent < end; extent+= innodb_buffer_pool_extent_size)
      for (buf_block_t *block= reinterpret_cast<buf_block_t*>(extent),
             *extent_end= block +
             pages_in_extent[srv_page_size_shift - UNIV_PAGE_SIZE_SHIFT_MIN];
           block < extent_end && reinterpret_cast<char*>(block) < end; block++)
      {
        MEM_MAKE_DEFINED(&block->page.lock, sizeof &block->page.lock);
        block->page.lock.free();
      }

    ut_dodump(memory_unaligned, size_unaligned);
#ifdef UNIV_PFS_MEMORY
    PSI_MEMORY_CALL(memory_free)(mem_key_buf_buf_pool, size, owner);
    owner= nullptr;
#endif
    os_total_large_mem_allocated-= size;
    my_virtual_mem_decommit(memory, size);
    my_virtual_mem_release(memory_unaligned, size_unaligned);
    memory= nullptr;
    memory_unaligned= nullptr;
  }

  pthread_cond_destroy(&done_flush_LRU);
  pthread_cond_destroy(&done_flush_list);
  pthread_cond_destroy(&do_flush_list);
  pthread_cond_destroy(&done_free);
```

### upstream storage/innobase/buf/buf0lru.cc:948-980
```c
buf_LRU_block_free_non_file_page(
/*=============================*/
	buf_block_t*	block)	/*!< in: block, must not contain a file page */
{
	void*		data;

	ut_ad(block->page.state() == buf_page_t::MEMORY);
#ifdef BTR_CUR_HASH_ADAPT
	assert_block_ahi_empty(block);
	block->n_hash_helps = 0;
#endif
	ut_ad(!block->page.in_free_list);
	ut_ad(!block->page.oldest_modification());
	ut_ad(!block->page.in_LRU_list);
	ut_ad(!block->page.hash);

	block->page.set_state(buf_page_t::NOT_USED);

	MEM_UNDEFINED(block->page.frame, srv_page_size);
	data = block->page.zip.data;

	if (data != NULL) {
		block->page.zip.data = NULL;
		ut_ad(block->zip_size());
		buf_buddy_free(data, block->zip_size());
		page_zip_set_size(&block->page.zip, 0);
	}

	if (buf_pool.to_withdraw() && buf_pool.withdraw(block->page)) {
	} else {
		UT_LIST_ADD_FIRST(buf_pool.free, &block->page);
		ut_d(block->page.in_free_list = true);
		buf_pool.try_LRU_scan= true;
```

### upstream storage/innobase/buf/buf0buf.cc:1262-1290
```c
buf_block_t *buf_pool_t::allocate() noexcept
{
  mysql_mutex_assert_owner(&mutex);

  while (buf_page_t *b= UT_LIST_GET_FIRST(free))
  {
    ut_ad(b->in_free_list);
    ut_d(b->in_free_list = FALSE);
    ut_ad(!b->oldest_modification());
    ut_ad(!b->in_LRU_list);
    ut_a(!b->in_file());
    UT_LIST_REMOVE(free, b);

    if (UNIV_LIKELY(!n_blocks_to_withdraw) || !withdraw(*b))
    {
      /* No adaptive hash index entries may point to a free block. */
      assert_block_ahi_empty(reinterpret_cast<buf_block_t*>(b));
      b->set_state(buf_page_t::MEMORY);
      b->set_os_used();
      return reinterpret_cast<buf_block_t*>(b);
    }
  }

  return nullptr;
}

/** Create the hash table.
@param n  the lower bound of n_cells */
void buf_pool_t::page_hash_table::create(ulint n) noexcept
```

### upstream storage/innobase/include/buf0buf.h:489-506
```c
  2 if modifications are pending, but the block is not in buf_pool.flush_list
  (because id().space() is the temporary tablespace). */
  Atomic_relaxed<lsn_t> oldest_modification_;

public:
  /** state() of unused block (in buf_pool.free list) */
  static constexpr uint32_t NOT_USED= 0;
  /** state() of block allocated as general-purpose memory */
  static constexpr uint32_t MEMORY= 1;
  /** state() of block that is being freed */
  static constexpr uint32_t REMOVE_HASH= 2;
  /** smallest state() of a buffer page that is freed in the tablespace */
  static constexpr uint32_t FREED= 3;
  /* unused state: 1U<<29 */
  /** smallest state() for a block that belongs to buf_pool.LRU */
  static constexpr uint32_t UNFIXED= 2U << 29;
  /** smallest state() of a (re)initialized page (no doublewrite needed) */
  static constexpr uint32_t REINIT= 3U << 29;
```

### upstream storage/innobase/buf/buf0buddy.cc:378-408
```c

/** Allocate a block from a bigger object.
@param[in]	buf		a block that is free to use
@param[in]	i		index of buf_pool.zip_free[]
@return allocated block */
static void *buf_buddy_alloc_from(void *buf, ulint i)
{
	ut_ad(i >= buf_buddy_get_slot(UNIV_ZIP_SIZE_MIN));
	ut_ad(i <= BUF_BUDDY_SIZES);
	ut_ad(!ut_align_offset(buf, srv_page_size));
	ut_ad(!buf_pool.contains_zip(buf, srv_page_size_shift));

	/* Add the unused parts of the block to the free lists. */
	for (ulint j = BUF_BUDDY_SIZES, offs = srv_page_size; j-- > i; ) {
		buf_buddy_free_t*	zip_buf;

		offs >>= 1;

		zip_buf = reinterpret_cast<buf_buddy_free_t*>(
			reinterpret_cast<byte*>(buf) + offs);
		buf_buddy_add_to_free(zip_buf, j);
	}

	buf_buddy_stamp_nonfree(reinterpret_cast<buf_buddy_free_t*>(buf), i);
	return(buf);
}

/** Allocate a ROW_FORMAT=COMPRESSED block.
@param i      index of buf_pool.zip_free[] or BUF_BUDDY_SIZES
@param lru    assigned to true if buf_pool.mutex was temporarily released
@return allocated block, never NULL */
```

### upstream dlmalloc/src/malloc.c:4921-4942
```c
static void* internal_memalign(mstate m, size_t alignment, size_t bytes) {
  void* mem = 0;
  if (alignment <  MIN_CHUNK_SIZE) /* must be at least a minimum chunk size */
    alignment = MIN_CHUNK_SIZE;
  if ((alignment & (alignment-SIZE_T_ONE)) != 0) {/* Ensure a power of 2 */
    size_t a = MALLOC_ALIGNMENT << 1;
    while (a < alignment) a <<= 1;
    alignment = a;
  }
  if (bytes >= MAX_REQUEST - alignment) {
    if (m != 0)  { /* Test isn't needed but avoids compiler warning */
      MALLOC_FAILURE_ACTION;
    }
  }
  else {
    size_t nb = request2size(bytes);
    size_t req = nb + alignment + MIN_CHUNK_SIZE - CHUNK_OVERHEAD;
    mem = internal_malloc(m, req);
    if (mem != 0) {
      mchunkptr p = mem2chunk(mem);
      if (PREACTION(m))
        return 0;
```

### upstream dlmalloc/src/malloc.c:5345-5375
```c
void* dlmemalign(size_t alignment, size_t bytes) {
  if (alignment <= MALLOC_ALIGNMENT) {
    return dlmalloc(bytes);
  }
  return internal_memalign(gm, alignment, bytes);
}

int dlposix_memalign(void** pp, size_t alignment, size_t bytes) {
  void* mem = 0;
  if (alignment == MALLOC_ALIGNMENT)
    mem = dlmalloc(bytes);
  else {
    size_t d = alignment / sizeof(void*);
    size_t r = alignment % sizeof(void*);
    if (r != 0 || d == 0 || (d & (d-SIZE_T_ONE)) != 0)
      return EINVAL;
    else if (bytes <= MAX_REQUEST - alignment) {
      if (alignment <  MIN_CHUNK_SIZE)
        alignment = MIN_CHUNK_SIZE;
      mem = internal_memalign(gm, alignment, bytes);
    }
  }
  if (mem == 0)
    return ENOMEM;
  else {
    *pp = mem;
    return 0;
  }
}

void* dlvalloc(size_t bytes) {
```

### upstream storage/innobase/include/univ.i:198-215
```c
/** log2 of largest page size (1<<16 == 65536 bytes). */
/** Maximum Page Size Shift (power of 2) */
#define UNIV_PAGE_SIZE_SHIFT_MAX	16U
/** log2 of default page size (1<<14 == 16384 bytes). */
/** Default Page Size Shift (power of 2) */
#define UNIV_PAGE_SIZE_SHIFT_DEF	14U
/** Original 16k InnoDB Page Size Shift, in case the default changes */
#define UNIV_PAGE_SIZE_SHIFT_ORIG	14U
/** Original 16k InnoDB Page Size as an ssize (log2 - 9) */
#define UNIV_PAGE_SSIZE_ORIG		(UNIV_PAGE_SIZE_SHIFT_ORIG - 9U)

/** Minimum page size InnoDB currently supports. */
#define UNIV_PAGE_SIZE_MIN	(1U << UNIV_PAGE_SIZE_SHIFT_MIN)
/** Maximum page size InnoDB currently supports. */
#define UNIV_PAGE_SIZE_MAX	(1U << UNIV_PAGE_SIZE_SHIFT_MAX)
/** Default page size for InnoDB tablespaces. */
#define UNIV_PAGE_SIZE_DEF	(1U << UNIV_PAGE_SIZE_SHIFT_DEF)
/** Original 16k page size for InnoDB tablespaces. */
```
