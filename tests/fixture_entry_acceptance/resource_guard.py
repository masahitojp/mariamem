"""Test-only P1 resource admission decision; observations are supplied by the campaign.

This module does not collect counters or stop a running workload. The campaign
must collect every counter and honor each STOP before starting a dependent case.
"""
class UnverifiedResource(ValueError):
    """A missing or unusable observation cannot authorize admission."""


def _number(mapping, key):
    value = mapping.get(key)
    if type(value) is not int or value < 0:
        raise UnverifiedResource(f'{key}: missing, negative, non-finite or invalid')
    return value


def evaluate(sample, limits, baseline_rss):
    """Return a STOP reason or None. Invalid observation raises UnverifiedResource.

    RSS is process-tree RSS, temp is linked allocation plus deduplicated unlinked
    allocation, and FD headroom is the minimum among every owned process.
    Required collectors must supply a complete, aligned observation; this
    calculation alone cannot establish its completeness or physical ownership.
    """
    baseline = _number({'baseline_rss': baseline_rss}, 'baseline_rss')
    rss = _number(sample, 'process_tree_rss_bytes')
    available = _number(sample, 'available_memory_bytes')
    linked = _number(sample, 'linked_allocated_bytes')
    unlinked = _number(sample, 'unlinked_allocated_bytes')
    disk_free = _number(sample, 'disk_free_bytes')
    children = _number(sample, 'active_children')
    connections = _number(sample, 'physical_connections')
    rss_limit = _number(limits, 'incremental_rss_ceiling_bytes')
    disk_limit = _number(limits, 'owned_disk_ceiling_bytes')
    disk_min = _number(limits, 'min_free_disk_bytes')
    fd_min = _number(limits, 'min_fd_headroom')
    child_limit = _number(limits, 'active_children_ceiling')
    connection_limit = _number(limits, 'physical_connections_ceiling')
    fds = sample.get('fd_by_process')
    if baseline <= 0 or rss <= 0 or available <= 0:
        raise UnverifiedResource('RSS and available memory must be positive')
    if not isinstance(fds, dict) or not fds:
        raise UnverifiedResource('missing FD census')
    for pid, row in fds.items():
        if not isinstance(pid, str) or not pid.isdecimal() or int(pid) <= 0 or not isinstance(row, dict):
            raise UnverifiedResource('invalid FD owner')
        count = _number(row, 'count')
        soft = _number(row, 'soft_limit')
        if count <= 0 or soft < count:
            raise UnverifiedResource('invalid FD count or limit')
    if rss - baseline > rss_limit:
        return 'incremental process-tree RSS guard'
    if linked + unlinked > disk_limit:
        return 'owned disk guard'
    if disk_free < disk_min:
        return 'free disk guard'
    if any(row['soft_limit'] - row['count'] < fd_min for row in fds.values()):
        return 'FD headroom guard'
    if children > child_limit:
        return 'active child guard'
    if connections > connection_limit:
        return 'physical connection guard'
    return None


class AdmissionStopped(RuntimeError):
    """An observed ceiling or an unverified counter prevented a new child."""


def admit(collect, limits, baseline_rss, operation):
    """Collect immediately before a test child and fail closed on bad evidence."""
    try:
        sample = collect()
        reason = evaluate(sample, limits, baseline_rss)
    except Exception as error:
        raise AdmissionStopped('UNVERIFIED resource observation; admission stopped') from error
    if reason is not None:
        raise AdmissionStopped(reason + '; admission stopped')
    return operation()
