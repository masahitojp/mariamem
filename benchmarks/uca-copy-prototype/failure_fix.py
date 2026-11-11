"""Small experimental prerequisite: propagate failure and clear readiness sentinel."""
def apply(text):
    old = '''                       (1<<MY_UCA_WEIGHT_LEVELS)-1)))
    return NULL; /* EOM or an error in rules */'''
    new = '''                       (1<<MY_UCA_WEIGHT_LEVELS)-1)))
  {
    /* Partial once_alloc buffers remain arena-owned. Do not publish a partial
       level[0].weights readiness sentinel to a later initialization attempt. */
    bzero(dst_uca, sizeof(*dst_uca));
    return NULL; /* EOM or an error in rules */
  }'''
    assert text.count(old) == 1
    text = text.replace(old, new)
    for ending in ['id1400', 'cs->number']:
        old = ending + ''')))
      goto ex;'''
        new = ending + ''')))
    {
      rc= 1;
      goto ex;
    }'''
        assert text.count(old) == 1
        text = text.replace(old, new)
    return text
