"""Small packaging invariant shared by local builds and distribution acceptance."""
from email.parser import BytesParser


def check_description(archive):
    names = [name for name in archive.namelist() if name.endswith('.dist-info/METADATA')]
    if len(names) != 1:
        raise ValueError('wheel must contain exactly one METADATA')
    metadata = BytesParser().parsebytes(archive.read(names[0]))
    if metadata.get('Description-Content-Type') != 'text/markdown' or not metadata.get_payload().strip():
        raise ValueError('wheel Markdown description is missing')
    return metadata
