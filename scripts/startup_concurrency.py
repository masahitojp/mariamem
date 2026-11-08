"""Guard the bounded startup-pool change before compiling the canonical guest."""
import hashlib


REGIONS = {
    'storage/innobase/buf/buf0dump.cc': (
        'srv_thread_pool->set_concurrency();\n\t\t\tbuf_load();\n'
        '\t\t\tsrv_thread_pool->set_concurrency();'),
    'storage/innobase/srv/srv0start.cc': (
        'srv_thread_pool->set_concurrency();\n\n'
        '\t\t\tmysql_mutex_lock(&recv_sys.mutex);\n'
        '\t\t\trecv_sys.apply(true);\n'
        '\t\t\tmysql_mutex_unlock(&recv_sys.mutex);\n\n'
        '\t\t\tsrv_thread_pool->set_concurrency();'),
}


def validate(source):
    """Require normal selection and retain the operation, lock and reset order."""
    hashes = {}
    for name, region in REGIONS.items():
        raw = (source / name).read_bytes()
        text = raw.decode()
        if (text.count(region) != 1 or
                text.count('srv_thread_pool->set_concurrency(') != 2 or
                'set_concurrency(srv_n_read_io_threads)' in text):
            raise ValueError('startup concurrency source contract changed: ' + name)
        hashes[name] = hashlib.sha256(raw).hexdigest()
    return {'contract': 'normal-startup-concurrency-v1',
            'selection': 'existing-default-with-existing-clamps',
            'files_sha256': hashes}
